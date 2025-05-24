#!/usr/bin/env python3
"""
LibGen Book Search and Download Script
Searches for books from books.txt and allows selective downloading
"""

import os
import re
import requests
from libgen_api import LibgenSearch
from urllib.parse import urlparse
import time

def parse_books_file(filename='books.txt'):
    """Parse the books.txt file and extract author and title"""
    books = []
    
    if not os.path.exists(filename):
        print(f"Error: {filename} not found!")
        return books
    
    with open(filename, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            # Parse format: "Author - Title"
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
    """Search for a book using libgen-api"""
    try:
        s = LibgenSearch()
        results = s.search_title(query)
        
        if not results:
            # Try searching by author if title search fails
            results = s.search_author(query)
        
        return results[:max_results]
    except Exception as e:
        print(f"Error searching for '{query}': {e}")
        return []

def format_results(results, prefer_pdf=True, prefer_newer=True):
    """Format and sort results, preferring PDF and newer editions"""
    if not results:
        return []
    
    # Filter and score results
    scored_results = []
    for result in results:
        score = 0
        
        # Prefer PDF format
        if prefer_pdf and result.get('Extension', '').lower() == 'pdf':
            score += 10
        
        # Prefer newer publications (if year is available)
        try:
            year = int(result.get('Year', 0))
            if year > 2000:
                score += (year - 2000) * 0.1
        except (ValueError, TypeError):
            pass
        
        # Prefer smaller file sizes (more reasonable for downloads)
        try:
            size_str = result.get('Size', '0')
            size_mb = parse_file_size(size_str)
            if 1 < size_mb < 100:  # Prefer books between 1MB and 100MB
                score += 5
        except:
            pass
        
        scored_results.append((score, result))
    
    # Sort by score (descending)
    scored_results.sort(key=lambda x: x[0], reverse=True)
    
    return [result for score, result in scored_results]

def parse_file_size(size_str):
    """Parse file size string to MB"""
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
            return float(size_str) / (1024 * 1024)  # Assume bytes
    except:
        return 0

def display_results(book_info, results):
    """Display search results in a formatted way"""
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
        
        print(f"\n{i}. {title}")
        print(f"   Author: {author}")
        print(f"   Year: {year} | Format: {extension} | Size: {size} | Pages: {pages}")
        
        # Show first few words of description if available
        desc = result.get('Descr', '')
        if desc and len(desc) > 100:
            desc = desc[:100] + "..."
        if desc:
            print(f"   Description: {desc}")

def get_download_links(result):
    """Get download links for a specific result"""
    try:
        s = LibgenSearch()
        download_links = s.resolve_download_links(result)
        return download_links
    except Exception as e:
        print(f"Error getting download links: {e}")
        return {}

def download_file(url, filename, chunk_size=8192):
    """Download a file from URL with progress indication"""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"\rDownloading {filename}: {progress:.1f}%", end='', flush=True)
        
        print(f"\n✓ Downloaded: {filename}")
        return True
        
    except Exception as e:
        print(f"\n✗ Error downloading {filename}: {e}")
        return False

def main():
    print("LibGen Book Search and Download Tool")
    print("=" * 40)
    
    # Parse books from file
    books = parse_books_file()
    if not books:
        print("No books found in books.txt")
        return
    
    print(f"Found {len(books)} books to search for.")
    
    # Search for each book and collect downloads
    downloads = []
    
    # Search for each book
    for book in books:
        print(f"\nSearching for: {book['original_line']}")
        
        # Try different search strategies
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
            time.sleep(1)  # Be nice to the API
        
        if results:
            formatted_results = format_results(results)
            display_results(book, formatted_results)
            
            # Ask for selection immediately after showing results
            print(f"\nSelect books to download for: {book['original_line']}")
            print("Enter numbers separated by commas (e.g., 1,3,5) or 'skip' to skip:")
            
            try:
                choice = input("> ").strip().lower()
                
                if choice != 'skip' and choice != '':
                    # Parse selection
                    selected_indices = []
                    for num_str in choice.split(','):
                        try:
                            num = int(num_str.strip())
                            if 1 <= num <= len(formatted_results):
                                selected_indices.append(num - 1)
                            else:
                                print(f"Invalid selection: {num}")
                        except ValueError:
                            print(f"Invalid input: {num_str}")
                    
                    # Add selected books to download list
                    for idx in selected_indices:
                        result = formatted_results[idx]
                        downloads.append({
                            'book': book,
                            'result': result
                        })
                        print(f"✓ Added: {result.get('Title', 'Unknown Title')}")
                        
            except KeyboardInterrupt:
                print("\nSelection cancelled.")
                break
        else:
            print(f"No results found for: {book['original_line']}")
    
    # Download all selected books at the end
    
    # Download selected books
    if downloads:
        print(f"\n{'='*80}")
        print(f"DOWNLOADING {len(downloads)} BOOKS")
        print(f"{'='*80}")
        
        download_dir = "downloaded_books"
        os.makedirs(download_dir, exist_ok=True)
        
        for i, download in enumerate(downloads, 1):
            book = download['book']
            result = download['result']
            
            print(f"\n[{i}/{len(downloads)}] Getting download links for:")
            print(f"  {result.get('Title', 'Unknown Title')} by {result.get('Author', 'Unknown Author')}")
            
            download_links = get_download_links(result)
            
            if not download_links:
                print("  ✗ No download links found")
                continue
            
            # Try to download from available links
            title = result.get('Title', 'Unknown')
            extension = result.get('Extension', 'pdf')
            
            # Clean filename
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
            filename = f"{safe_title}.{extension}"
            filepath = os.path.join(download_dir, filename)
            
            downloaded = False
            for link_name, url in download_links.items():
                if url:
                    print(f"  Trying {link_name}...")
                    if download_file(url, filepath):
                        downloaded = True
                        break
                    time.sleep(2)  # Wait between attempts
            
            if not downloaded:
                print(f"  ✗ Failed to download from all available links")
        
        print(f"\nDownloads completed! Check the '{download_dir}' folder.")
    else:
        print("\nNo books selected for download.")

if __name__ == "__main__":
    # Check if libgen-api is installed
    try:
        import libgen_api
    except ImportError:
        print("Error: libgen-api not installed.")
        print("Install it with: pip install libgen-api")
        exit(1)
    
    main()
