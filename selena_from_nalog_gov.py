#!/usr/bin/env python3
"""
Balance Sheet Downloader for bo.nalog.gov.ru
Automated download of balance sheet archives by INN using Selenium 4+
"""

import os
import sys
import time
import logging
import zipfile
import random
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple
from dataclasses import dataclass
from contextlib import contextmanager

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    WebDriverException,
    ElementClickInterceptedException
)
from webdriver_manager.chrome import ChromeDriverManager
from tenacity import retry, stop_after_attempt, wait_exponential


@dataclass
class DownloadResult:
    """Results of a download operation"""
    inn: str
    year: Optional[str]
    success: bool
    file_path: Optional[str]
    error_message: Optional[str]
    timestamp: datetime


class BalanceSheetDownloader:
    """Main class for downloading balance sheets from bo.nalog.gov.ru"""
    
    def __init__(self, download_dir: str = "downloads", headless: bool = True):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        self.headless = headless
        self.driver = None
        self.wait = None
        self.setup_logging()
        
    def setup_logging(self):
        """Configure logging for the application"""
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[
                logging.FileHandler('balance_sheet_downloader.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    @contextmanager
    def get_driver(self):
        """Context manager for WebDriver lifecycle"""
        try:
            self.driver = self._create_driver()
            self.wait = WebDriverWait(self.driver, 20)
            yield self.driver
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None
                self.wait = None
    
    def _create_driver(self) -> webdriver.Chrome:
        """Create and configure Chrome WebDriver"""
        options = Options()
        
        # Download preferences
        prefs = {
            "download.default_directory": str(self.download_dir.absolute()),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_settings.popups": 0,
        }
        options.add_experimental_option("prefs", prefs)
        
        # Chrome options for stability
        if self.headless:
            options.add_argument("--headless")
        
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Create driver with automatic driver management
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # Remove automation indicators
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    
    def random_delay(self, min_seconds: float = 1.0, max_seconds: float = 3.0):
        """Add randomized delay to avoid detection"""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def search_organization(self, inn: str) -> bool:
        """Search for organization by INN"""
        try:
            search_url = f"https://bo.nalog.gov.ru/search?query={inn}"
            self.logger.info(f"Searching for INN: {inn}")
            
            self.driver.get(search_url)
            self.random_delay(2, 4)
            
            # Wait for search results to load
            results_container = self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "results-search-table-item"))
            )
            
            # Find the matching INN entry
            inn_elements = self.driver.find_elements(By.TAG_NAME, "ins")
            for element in inn_elements:
                if element.text.strip() == inn:
                    self.logger.info(f"Found matching INN: {inn}")
                    element.click()
                    self.random_delay(2, 4)
                    return True
            
            self.logger.warning(f"INN {inn} not found in search results")
            return False
            
        except TimeoutException:
            self.logger.error(f"Timeout waiting for search results for INN: {inn}")
            return False
        except Exception as e:
            self.logger.error(f"Error searching for INN {inn}: {str(e)}")
            return False
    
    def download_reports(self, inn: str, year: Optional[str] = None) -> List[DownloadResult]:
        """Download balance sheet reports for specified year or all years"""
        results = []
        
        try:
            # Wait for organization page to load
            self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "download-reports-wrapper"))
            )
            
            # Click "Скачать таблицей или текстом"
            download_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Скачать таблицей или текстом')]"))
            )
            download_button.click()
            self.random_delay(1, 2)
            
            # Handle popup
            popup_result = self._handle_download_popup(inn, year)
            if popup_result:
                results.append(popup_result)
                
            # If no specific year requested, also download 2023 specifically
            if year is None:
                year_2023_result = self._download_specific_year(inn, "2023")
                if year_2023_result:
                    results.append(year_2023_result)
            
        except Exception as e:
            self.logger.error(f"Error downloading reports for INN {inn}: {str(e)}")
            results.append(DownloadResult(
                inn=inn,
                year=year,
                success=False,
                file_path=None,
                error_message=str(e),
                timestamp=datetime.now()
            ))
        
        return results
    
    def _handle_download_popup(self, inn: str, year: Optional[str]) -> Optional[DownloadResult]:
        """Handle the download popup window"""
        try:
            # Wait for popup to appear
            self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "download-reports-buttons"))
            )
            
            # Click "Выбрать все"
            select_all_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[@data-action='add' and contains(text(), 'Выбрать все')]"))
            )
            select_all_button.click()
            self.random_delay(1, 2)
            
            # Click "Скачать архив"
            download_archive_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Скачать архив')]"))
            )
            
            # Get initial file count
            initial_files = self._get_download_files()
            
            download_archive_button.click()
            self.random_delay(3, 5)
            
            # Wait for download to complete
            downloaded_file = self._wait_for_download(initial_files)
            
            if downloaded_file:
                organized_path = self._organize_download(downloaded_file, inn, year or "all")
                
                if self._verify_download(organized_path):
                    return DownloadResult(
                        inn=inn,
                        year=year or "all",
                        success=True,
                        file_path=str(organized_path),
                        error_message=None,
                        timestamp=datetime.now()
                    )
                else:
                    return DownloadResult(
                        inn=inn,
                        year=year or "all",
                        success=False,
                        file_path=None,
                        error_message="Download verification failed",
                        timestamp=datetime.now()
                    )
            
        except Exception as e:
            self.logger.error(f"Error in download popup for INN {inn}: {str(e)}")
            return DownloadResult(
                inn=inn,
                year=year,
                success=False,
                file_path=None,
                error_message=str(e),
                timestamp=datetime.now()
            )
        
        return None
    
    def _download_specific_year(self, inn: str, year: str) -> Optional[DownloadResult]:
        """Download reports for a specific year"""
        try:
            # Click year button
            year_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, f"//button[@data-year='{year}' and contains(text(), '{year}')]"))
            )
            year_button.click()
            self.random_delay(1, 2)
            
            # Click "Выбрать все" for the year
            select_all_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[@data-action='add' and contains(text(), 'Выбрать все')]"))
            )
            select_all_button.click()
            self.random_delay(1, 2)
            
            # Click "Скачать архив"
            download_archive_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Скачать архив')]"))
            )
            
            initial_files = self._get_download_files()
            download_archive_button.click()
            self.random_delay(3, 5)
            
            downloaded_file = self._wait_for_download(initial_files)
            
            if downloaded_file:
                organized_path = self._organize_download(downloaded_file, inn, year)
                
                if self._verify_download(organized_path):
                    return DownloadResult(
                        inn=inn,
                        year=year,
                        success=True,
                        file_path=str(organized_path),
                        error_message=None,
                        timestamp=datetime.now()
                    )
            
        except Exception as e:
            self.logger.error(f"Error downloading {year} reports for INN {inn}: {str(e)}")
            return DownloadResult(
                inn=inn,
                year=year,
                success=False,
                file_path=None,
                error_message=str(e),
                timestamp=datetime.now()
            )
        
        return None
    
    def _get_download_files(self) -> List[str]:
        """Get list of current files in download directory"""
        return [f.name for f in self.download_dir.iterdir() if f.is_file()]
    
    def _wait_for_download(self, initial_files: List[str], timeout: int = 30) -> Optional[str]:
        """Wait for new file to appear in download directory"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            current_files = self._get_download_files()
            new_files = [f for f in current_files if f not in initial_files]
            
            if new_files:
                # Wait a bit more to ensure download is complete
                time.sleep(2)
                new_file = new_files[0]
                
                # Check if file is complete (not partial download)
                if not new_file.endswith('.crdownload') and not new_file.endswith('.tmp'):
                    return new_file
            
            time.sleep(1)
        
        return None
    
    def _organize_download(self, filename: str, inn: str, year: str) -> Path:
        """Organize downloaded file into proper directory structure"""
        source_path = self.download_dir / filename
        
        # Create directory structure: downloads/INN/year/
        target_dir = self.download_dir / inn / year
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename if file already exists
        base_name = source_path.stem
        extension = source_path.suffix
        counter = 1
        
        target_path = target_dir / filename
        while target_path.exists():
            target_path = target_dir / f"{base_name}_{counter}{extension}"
            counter += 1
        
        # Move file to organized location
        source_path.rename(target_path)
        
        return target_path
    
    def _verify_download(self, file_path: Path) -> bool:
        """Verify downloaded file integrity"""
        try:
            if not file_path.exists():
                self.logger.error(f"File does not exist: {file_path}")
                return False
            
            # Check file size
            if file_path.stat().st_size == 0:
                self.logger.error(f"File is empty: {file_path}")
                return False
            
            # If it's a ZIP file, verify ZIP integrity
            if file_path.suffix.lower() == '.zip':
                try:
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        # Test ZIP integrity
                        bad_file = zip_ref.testzip()
                        if bad_file:
                            self.logger.error(f"ZIP file corrupted, first bad file: {bad_file}")
                            return False
                        
                        # Check for .xlsx files in ZIP
                        xlsx_files = [f for f in zip_ref.namelist() if f.endswith('.xlsx')]
                        if not xlsx_files:
                            self.logger.warning(f"No .xlsx files found in ZIP: {file_path}")
                        else:
                            self.logger.info(f"Found {len(xlsx_files)} .xlsx files in ZIP")
                    
                except zipfile.BadZipFile:
                    self.logger.error(f"Invalid ZIP file: {file_path}")
                    return False
            
            self.logger.info(f"File verification passed: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error verifying file {file_path}: {str(e)}")
            return False
    
    def process_inns(self, inns_file: str) -> List[DownloadResult]:
        """Process all INNs from the input file"""
        if not Path(inns_file).exists():
            self.logger.error(f"INNs file not found: {inns_file}")
            return []
        
        # Read INNs from file
        with open(inns_file, 'r', encoding='utf-8') as f:
            inns = [line.strip() for line in f if line.strip()]
        
        self.logger.info(f"Processing {len(inns)} INNs from {inns_file}")
        
        all_results = []
        
        with self.get_driver():
            for i, inn in enumerate(inns, 1):
                self.logger.info(f"Processing INN {i}/{len(inns)}: {inn}")
                
                try:
                    # Search for organization
                    if self.search_organization(inn):
                        # Download reports
                        results = self.download_reports(inn)
                        all_results.extend(results)
                        
                        # Log results for this INN
                        for result in results:
                            if result.success:
                                self.logger.info(f"Successfully downloaded {result.year} reports for INN {inn}: {result.file_path}")
                            else:
                                self.logger.error(f"Failed to download {result.year} reports for INN {inn}: {result.error_message}")
                    else:
                        all_results.append(DownloadResult(
                            inn=inn,
                            year=None,
                            success=False,
                            file_path=None,
                            error_message="Organization not found",
                            timestamp=datetime.now()
                        ))
                
                except Exception as e:
                    self.logger.error(f"Error processing INN {inn}: {str(e)}")
                    all_results.append(DownloadResult(
                        inn=inn,
                        year=None,
                        success=False,
                        file_path=None,
                        error_message=str(e),
                        timestamp=datetime.now()
                    ))
                
                # Add delay between INNs
                self.random_delay(5, 10)
        
        return all_results
    
    def generate_report(self, results: List[DownloadResult]) -> str:
        """Generate summary report of download results"""
        total_inns = len(set(r.inn for r in results))
        successful_downloads = len([r for r in results if r.success])
        failed_downloads = len([r for r in results if not r.success])
        
        report = f"""
Balance Sheet Download Summary Report
=====================================
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Total INNs processed: {total_inns}
Successful downloads: {successful_downloads}
Failed downloads: {failed_downloads}
Success rate: {(successful_downloads / len(results) * 100):.1f}%

Detailed Results:
"""
        
        for result in results:
            status = "✓" if result.success else "✗"
            report += f"{status} {result.inn} ({result.year or 'all'}): {result.file_path or result.error_message}\n"
        
        return report


def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Download balance sheets from bo.nalog.gov.ru')
    parser.add_argument('inns_file', help='Path to file containing INNs (one per line)')
    parser.add_argument('--download-dir', default='downloads', help='Download directory')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    parser.add_argument('--report', default='download_report.txt', help='Report file path')
    
    args = parser.parse_args()
    
    # Create downloader instance
    downloader = BalanceSheetDownloader(
        download_dir=args.download_dir,
        headless=args.headless
    )
    
    try:
        # Process all INNs
        results = downloader.process_inns(args.inns_file)
        
        # Generate and save report
        report = downloader.generate_report(results)
        
        with open(args.report, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"Download process completed. Report saved to: {args.report}")
        print(f"Total results: {len(results)}")
        print(f"Successful downloads: {len([r for r in results if r.success])}")
        
    except KeyboardInterrupt:
        print("\nDownload process interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
