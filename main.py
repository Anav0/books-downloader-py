#!/usr/bin/env python3

import os
import re
import requests
from libgen_api import LibgenSearch
from urllib.parse import urlparse
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

def parse_books_file(filename='books.txt'):
    books = []
    
    if not os.path.exists(filename):
        print(f"Error: {filename} not found!")
        return books
    
    with open(filename, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            if ' - ' in line:
                author, title = line.split(' - ', 1)
                books.append({
                    'author': author.strip(),
                    'title': title.strip(),
                    'original_line': line
                })
            else:
                print(f"Warning: Line {line_num} doesn't match expected format: {line}")
    
    return books

def search_book(query, max_results=10):
    try:
        s = LibgenSearch()
        results = s.search_title(query)
        
        if not results:
            results = s.search_author(query)
        
        return results[:max_results]
    except Exception as e:
        print(f"Error searching for '{query}': {e}")
        return []

def format_results(results, prefer_pdf=True, prefer_newer=True):
    if not results:
        return []
    
    scored_results = []
    for result in results:
        score = 0
        
        if prefer_pdf and result.get('Extension', '').lower() == 'pdf':
            score += 10
        
        try:
            year = int(result.get('Year', 0))
            if year > 2000:
                score += (year - 2000) * 0.1
        except (ValueError, TypeError):
            pass
        
        try:
            size_str = result.get('Size', '0')
            size_mb = parse_file_size(size_str)
            if 1 < size_mb < 100:
                score += 5
        except:
            pass
        
        scored_results.append((score, result))
    
    scored_results.sort(key=lambda x: x[0], reverse=True)
    
    return [result for score, result in scored_results]

def parse_file_size(size_str):
    if not size_str:
        return 0
    
    size_str = size_str.lower()
    try:
        if 'kb' in size_str:
            return float(size_str.replace('kb', '').strip()) / 1024
        elif 'mb' in size_str:
            return float(size_str.replace('mb', '').strip())
        elif 'gb' in size_str:
            return float(size_str.replace('gb', '').strip()) * 1024
        else:
            return float(size_str) / (1024 * 1024)
    except:
        return 0

def display_results(book_info, results):
    print(f"\n{'='*80}")
    print(f"Results for: {book_info['original_line']}")
    print(f"{'='*80}")
    
    if not results:
        print("No results found.")
        return
    
    for i, result in enumerate(results, 1):
        title = result.get('Title', 'Unknown Title')
        author = result.get('Author', 'Unknown Author')
        year = result.get('Year', 'Unknown')
        extension = result.get('Extension', 'Unknown')
        size = result.get('Size', 'Unknown')
        pages = result.get('Pages', 'Unknown')
        publisher = result.get('Publisher', 'Unknown')
        
        print(f"\n{i}. {title}")
        print(f"   Author: {author}")
        print(f"   Publisher: {publisher}")
        print(f"   Year: {year} | Format: {extension} | Size: {size} | Pages: {pages}")
        
        desc = result.get('Descr', '')
        if desc and len(desc) > 100:
            desc = desc[:100] + "..."
        if desc:
            print(f"   Description: {desc}")

def get_download_links(result):
    try:
        s = LibgenSearch()
        download_links = s.resolve_download_links(result)
        return download_links
    except Exception as e:
        print(f"Error getting download links: {e}")
        return {}

def download_file(url, filename, chunk_size=8192):
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
        
        return True, filename
        
    except Exception as e:
        return False, f"Error downloading {filename}: {e}"

def download_single_book(download_item, download_dir):
    book = download_item['book']
    result = download_item['result']
    
    book_title = result.get('Title', 'Unknown Title')
    book_author = result.get('Author', 'Unknown Author')
    
    try:
        download_links = get_download_links(result)
        
        if not download_links:
            return False, book['original_line'], f"No download links found for {book_title}"
        
        extension = result.get('Extension', 'pdf')
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', book['original_line'])
        filename = f"{safe_title}.{extension}"
        filepath = os.path.join(download_dir, filename)
        
        for link_name, url in download_links.items():
            if url:
                success, message = download_file(url, filepath)
                if success:
                    return True, book['original_line'], f"Downloaded: {filename}"
                time.sleep(1)
        
        return False, book['original_line'], f"Failed to download from all available links"
        
    except Exception as e:
        return False, book['original_line'], f"Error processing {book_title}: {e}"

def main():
    print("LibGen Book Search and Download Tool")
    print("=" * 40)
    
    books = parse_books_file()
    if not books:
        print("No books found in books.txt")
        return
    
    print(f"Found {len(books)} books to search for.")
    
    downloads = []
    not_found = []
    not_downloaded = []
    total_books = len(books)
    
    for book_num, book in enumerate(books, 1):
        print(f"\n[{book_num}/{total_books}] Searching for: {book['original_line']}")
        
        search_queries = [
            f"{book['author']} {book['title']}",
            book['title'],
            book['author']
        ]
        
        results = []
        for query in search_queries:
            results = search_book(query)
            if results:
                break
            time.sleep(1)
        
        if results:
            formatted_results = format_results(results)
            display_results(book, formatted_results)
            
            print(f"\nSelect books to download for: {book['original_line']}")
            print(f"Enter numbers separated by commas (e.g., 1,3,5) or 'skip' to skip:")
            print(f"Progress: Selected {len(downloads)} books so far ({book_num}/{total_books} books processed)")
            
            while True:
                try:
                    choice = input("> ").strip().lower()
                    
                    if choice == 'skip' or choice == '':
                        break
                    
                    selected_indices = []
                    invalid_selections = []
                    
                    for num_str in choice.split(','):
                        try:
                            num = int(num_str.strip())
                            if 1 <= num <= len(formatted_results):
                                selected_indices.append(num - 1)
                            else:
                                invalid_selections.append(num_str.strip())
                        except ValueError:
                            invalid_selections.append(num_str.strip())
                    
                    if invalid_selections:
                        print(f"Invalid selection(s): {', '.join(invalid_selections)}")
                        print(f"Please enter numbers between 1 and {len(formatted_results)}, or 'skip':")
                        continue
                    
                    if selected_indices:
                        for idx in selected_indices:
                            result = formatted_results[idx]
                            downloads.append({
                                'book': book,
                                'result': result
                            })
                            print(f"✓ Added: {result.get('Title', 'Unknown Title')}")
                    
                    break
                        
                except KeyboardInterrupt:
                    print("\nSelection cancelled.")
                    return
        else:
            print(f"No results found for: {book['original_line']}")
            not_found.append(book['original_line'])
    
    if downloads:
        print(f"\n{'='*80}")
        print(f"DOWNLOADING {len(downloads)} BOOKS")
        print(f"{'='*80}")
        
        download_dir = "downloaded_books"
        os.makedirs(download_dir, exist_ok=True)
        
        print(f"Starting download of {len(downloads)} books using multithreading...")
        print("This may take a while depending on file sizes and connection speed.\n")
        
        successful_downloads = []
        failed_downloads = []
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_book = {
                executor.submit(download_single_book, download, download_dir): download 
                for download in downloads
            }
            
            completed = 0
            for future in as_completed(future_to_book):
                completed += 1
                success, book_name, message = future.result()
                
                if success:
                    print(f"[{completed}/{len(downloads)}] ✓ {message}")
                    successful_downloads.append(book_name)
                else:
                    print(f"[{completed}/{len(downloads)}] ✗ {message}")
                    failed_downloads.append(book_name)
        
        print(f"\nDownload Summary:")
        print(f"✓ Successfully downloaded: {len(successful_downloads)}")
        print(f"✗ Failed to download: {len(failed_downloads)}")
        print(f"Check the '{download_dir}' folder for downloaded files.")
        
        not_downloaded.extend(failed_downloads)
        
        if not_found:
            print(f"\n📚 Books not found ({len(not_found)}):")
            for book in not_found:
                print(f"  - {book}")
        
        if not_downloaded:
            print(f"\n❌ Books found but failed to download ({len(not_downloaded)}):")
            for book in not_downloaded:
                print(f"  - {book}")
        
        if not_found or not_downloaded:
            print(f"\nWould you like to save the missing books to 'missing.txt'? (y/n)")
            try:
                save_choice = input("> ").strip().lower()
                if save_choice in ['y', 'yes']:
                    with open('missing.txt', 'w', encoding='utf-8') as f:
                        if not_found:
                            f.write("# Books not found in LibGen:\n")
                            for book in not_found:
                                f.write(f"{book}\n")
                            f.write("\n")
                        
                        if not_downloaded:
                            f.write("# Books found but failed to download:\n")
                            for book in not_downloaded:
                                f.write(f"{book}\n")
                    
                    print("✓ Missing books saved to 'missing.txt'")
            except KeyboardInterrupt:
                print("\nSkipped saving missing books.")
        
        if not not_found and not not_downloaded:
            print("🎉 All selected books downloaded successfully!")
    else:
        print("\nNo books selected for download.")
        
        if not_found:
            print(f"\n📚 Books not found ({len(not_found)}):")
            for book in not_found:
                print(f"  - {book}")
            
            print(f"\nWould you like to save the missing books to 'missing.txt'? (y/n)")
            try:
                save_choice = input("> ").strip().lower()
                if save_choice in ['y', 'yes']:
                    with open('missing.txt', 'w', encoding='utf-8') as f:
                        f.write("# Books not found in LibGen:\n")
                        for book in not_found:
                            f.write(f"{book}\n")
                    
                    print("✓ Missing books saved to 'missing.txt'")
            except KeyboardInterrupt:
                print("\nSkipped saving missing books.")

if __name__ == "__main__":
    try:
        import libgen_api
    except ImportError:
        print("Error: libgen-api not installed.")
        print("Install it with: pip install libgen-api")
        exit(1)
    
    main()
