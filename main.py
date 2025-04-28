import json
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from typing import List, Dict, Any, Optional

from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent, ItemEnterEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.HideWindowAction import HideWindowAction
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction
from ulauncher.api.shared.action.SetUserQueryAction import SetUserQueryAction
from ulauncher.api.shared.action.OpenUrlAction import OpenUrlAction


class PinboardExtension(Extension):
    def __init__(self):
        super().__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
        self.subscribe(ItemEnterEvent, ItemEnterEventListener())
        self.selected_tags = []
        self.cache = {}
        self.last_cache_time = None
        self.error_message = None
        self.current_view = None  # Pode ser 'main', 'tags', 'recent', ou 'search'

    def get_token(self):
        return self.preferences.get('pinboard_token', '')

    def get_bookmarks(self, tag=''):
        """Get bookmarks from Pinboard API"""
        if not self.get_token():
            return []
            
        # Use cache if available and less than 5 minutes old
        cache_key = f'bookmarks_{tag}'
        current_time = datetime.now()
        if (self.last_cache_time and 
            (current_time - self.last_cache_time).total_seconds() < 300 and
            cache_key in self.cache):
            return self.cache[cache_key]
            
        # Not in cache, fetch from API
        url = f'https://api.pinboard.in/v1/posts/all?auth_token={self.get_token()}&format=json'
        if tag:
            url += f'&tag={urllib.parse.quote(tag)}'
            
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                bookmarks = json.loads(response.read())
                self.cache[cache_key] = bookmarks
                self.last_cache_time = current_time
                self.error_message = None
                return bookmarks
        except Exception as e:
            self.error_message = str(e)
            return []

    def get_recent_bookmarks(self, count=20):
        """Get recent bookmarks from Pinboard API"""
        if not self.get_token():
            return []
            
        # Use cache if available and less than 5 minutes old
        cache_key = 'recent_bookmarks'
        current_time = datetime.now()
        if (self.last_cache_time and 
            (current_time - self.last_cache_time).total_seconds() < 300 and
            cache_key in self.cache):
            return self.cache[cache_key]
            
        # Not in cache, fetch from API
        url = f'https://api.pinboard.in/v1/posts/recent?auth_token={self.get_token()}&format=json&count={count}'
            
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read())
                bookmarks = data.get('posts', [])
                self.cache[cache_key] = bookmarks
                self.last_cache_time = current_time
                self.error_message = None
                return bookmarks
        except Exception as e:
            self.error_message = str(e)
            return []

    def get_tags(self):
        """Get tags from Pinboard API"""
        if not self.get_token():
            return []
            
        # Use cache if available and less than 5 minutes old
        cache_key = 'tags'
        current_time = datetime.now()
        if (self.last_cache_time and 
            (current_time - self.last_cache_time).total_seconds() < 300 and
            cache_key in self.cache):
            return self.cache[cache_key]
            
        # Not in cache, fetch from API
        url = f'https://api.pinboard.in/v1/tags/get?auth_token={self.get_token()}&format=json'
            
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                tags_data = json.loads(response.read())
                tags = [{'name': tag, 'count': count} for tag, count in tags_data.items()]
                tags.sort(key=lambda x: x['count'], reverse=True)
                self.cache[cache_key] = tags
                self.last_cache_time = current_time
                self.error_message = None
                return tags
        except Exception as e:
            self.error_message = str(e)
            return []

    def add_bookmark(self, url, title, description='', tags=None):
        if not self.get_token() or not url:
            return False

        tags_str = ','.join(tags) if tags else ''
        params = {
            'auth_token': self.get_token(),
            'url': url,
            'description': title,
            'extended': description,
            'tags': tags_str,
            'replace': 'yes',
            'shared': 'no'
        }

        query_string = urllib.parse.urlencode(params)
        api_url = f'https://api.pinboard.in/v1/posts/add?{query_string}'

        try:
            with urllib.request.urlopen(api_url, timeout=10) as response:
                result = json.loads(response.read())
                self.cache = {}  # Reset cache
                self.last_cache_time = None
                self.error_message = None
                return result.get('result_code') == 'done'
        except Exception as e:
            self.error_message = str(e)
            return False


class KeywordQueryEventListener(EventListener):
    def on_event(self, event, extension):
        query = event.get_argument() or ""
        items = []

        if not extension.get_token():
            return RenderResultListAction([
                ExtensionResultItem(
                    icon='images/icon.png',
                    name='Pinboard API Token Required',
                    description='Please set your Pinboard API token in the extension preferences',
                    on_enter=HideWindowAction()
                )
            ])

        # Main menu (if no further input)
        if not query:
            extension.current_view = 'main'
            
            # Search bookmarks item
            search_description = "Search all bookmarks"
            if extension.selected_tags:
                search_description = f"Search bookmarks with tags: {', '.join(extension.selected_tags)}"
            
            items.append(ExtensionResultItem(
                icon='images/icon.png',
                name='Search Bookmarks',
                description=search_description,
                on_enter=ExtensionCustomAction({
                    'action': 'search_bookmarks',
                    'tags': extension.selected_tags
                }, keep_app_open=True)
            ))
            
            # Browse tags item
            items.append(ExtensionResultItem(
                icon='images/tag.png',
                name='Browse Tags',
                description='View and select tags to filter your bookmarks',
                on_enter=ExtensionCustomAction({
                    'action': 'browse_tags'
                }, keep_app_open=True)
            ))
            
            # Browse recent bookmarks item
            items.append(ExtensionResultItem(
                icon='images/icon.png',
                name='Browse Recent Bookmarks',
                description='View your most recent Pinboard bookmarks',
                on_enter=ExtensionCustomAction({
                    'action': 'browse_recent'
                }, keep_app_open=True)
            ))
            
            # Add new bookmark item
            items.append(ExtensionResultItem(
                icon='images/icon.png',
                name='Add New Bookmark',
                description='Save current URL to Pinboard',
                on_enter=ExtensionCustomAction({
                    'action': 'add_bookmark'
                }, keep_app_open=True)
            ))
            
            return RenderResultListAction(items)
        
        # Handle tag browsing with # prefix
        if query.startswith("#"):
            extension.current_view = 'tags'
            tags = extension.get_tags()
            
            # Filter tags by query
            tag_query = query[1:].lower().strip()
            filtered_tags = tags
            
            if tag_query:
                filtered_tags = [tag for tag in tags if tag_query in tag['name'].lower()]
            
            # Limit the number of results
            max_display = 50
            count_total = len(filtered_tags)
            
            for tag in filtered_tags[:max_display]:
                is_selected = tag['name'] in extension.selected_tags
                action_data = {
                    'action': 'toggle_tag',
                    'tag': tag['name'],
                    'is_selected': is_selected
                }
                
                items.append(ExtensionResultItem(
                    icon='images/tag_selected.png' if is_selected else 'images/tag.png',
                    name=f"{'✓ ' if is_selected else ''}{tag['name']}",
                    description=f"{tag['count']} bookmarks",
                    on_enter=ExtensionCustomAction(action_data, keep_app_open=True)
                ))
            
            if count_total > max_display:
                items.append(ExtensionResultItem(
                    icon='images/tag.png',
                    name=f"... and {count_total - max_display} more tags",
                    description="Type to filter results",
                    on_enter=HideWindowAction()
                ))
            
            if not items:
                items.append(ExtensionResultItem(
                    icon='images/tag.png',
                    name='No matching tags found',
                    description='Try a different search term',
                    on_enter=HideWindowAction()
                ))
            
            return RenderResultListAction(items)
            
        # Check if we're in the Recent Bookmarks view
        if extension.current_view == 'recent':
            # Browse only recent bookmarks
            recent_bookmarks = extension.get_recent_bookmarks()
            
            # Filter recent bookmarks by query
            filtered_bookmarks = [b for b in recent_bookmarks if 
                        query.lower() in b.get('description', '').lower() or
                        query.lower() in b.get('extended', '').lower() or
                        query.lower() in b.get('href', '').lower()]
            
            # Create result items
            for bookmark in filtered_bookmarks:
                items.append(ExtensionResultItem(
                    icon='images/icon.png',
                    name=bookmark.get('description', 'No title'),
                    description=bookmark.get('href', 'No URL'),
                    on_enter=OpenUrlAction(bookmark.get('href', ''))
                ))
            
            if not items:
                # Check if there was an error
                if extension.error_message:
                    error_item = ExtensionResultItem(
                        icon='images/icon.png',
                        name='Error loading recent bookmarks',
                        description=f'Error: {extension.error_message}',
                        on_enter=HideWindowAction()
                    )
                    return RenderResultListAction([error_item])
                else:
                    items.append(ExtensionResultItem(
                        icon='images/icon.png',
                        name='No matching recent bookmarks found',
                        description='Try a different search term',
                        on_enter=HideWindowAction()
                    ))
            
            return RenderResultListAction(items)
        
        # Default: Search bookmarks (normal search mode)
        extension.current_view = 'search'
        bookmarks = []
        
        if extension.selected_tags:
            # Search in each selected tag's bookmarks
            for tag in extension.selected_tags:
                tag_bookmarks = extension.get_bookmarks(tag)
                for bookmark in tag_bookmarks:
                    if (query.lower() in bookmark.get('description', '').lower() or 
                        query.lower() in bookmark.get('extended', '').lower() or
                        query.lower() in bookmark.get('href', '').lower()):
                        bookmarks.append(bookmark)
        else:
            # Search all bookmarks
            all_bookmarks = extension.get_bookmarks()
            bookmarks = [b for b in all_bookmarks if 
                        query.lower() in b.get('description', '').lower() or
                        query.lower() in b.get('extended', '').lower() or
                        query.lower() in b.get('href', '').lower()]
        
        # Create result items
        for bookmark in bookmarks:
            items.append(ExtensionResultItem(
                icon='images/icon.png',
                name=bookmark.get('description', 'No title'),
                description=bookmark.get('href', 'No URL'),
                on_enter=OpenUrlAction(bookmark.get('href', ''))
            ))
        
        if not items:
            # Check if there was an error
            if extension.error_message:
                error_item = ExtensionResultItem(
                    icon='images/icon.png',
                    name='Error loading bookmarks',
                    description=f'Error: {extension.error_message}',
                    on_enter=HideWindowAction()
                )
                return RenderResultListAction([error_item])
            else:
                items.append(ExtensionResultItem(
                    icon='images/icon.png',
                    name='No matching bookmarks found',
                    description='Try a different search term',
                    on_enter=HideWindowAction()
                ))
        
        return RenderResultListAction(items)


class ItemEnterEventListener(EventListener):
    def on_event(self, event, extension):
        data = event.get_data()
        action = data.get('action')
        items = []

        if action == 'search_bookmarks':
            # Set user query to empty to start search
            extension.current_view = 'search'
            return SetUserQueryAction(extension.preferences['pinboard_kw'])
        
        elif action == 'browse_tags':
            # Show tag browser
            extension.current_view = 'tags'
            return SetUserQueryAction(f"{extension.preferences['pinboard_kw']} #")
        
        elif action == 'browse_recent':
            # Show recent bookmarks view
            extension.current_view = 'recent'
            
            # Get recent bookmarks
            recent_bookmarks = extension.get_recent_bookmarks()
            
            if not recent_bookmarks and extension.error_message:
                # Show error
                return RenderResultListAction([
                    ExtensionResultItem(
                        icon='images/icon.png',
                        name='Error loading recent bookmarks',
                        description=f'Error: {extension.error_message}',
                        on_enter=HideWindowAction()
                    )
                ])
            
            # Create result items for recent bookmarks
            for bookmark in recent_bookmarks:
                items.append(ExtensionResultItem(
                    icon='images/icon.png',
                    name=bookmark.get('description', 'No title'),
                    description=bookmark.get('href', 'No URL'),
                    on_enter=OpenUrlAction(bookmark.get('href', ''))
                ))
            
            if not items:
                items.append(ExtensionResultItem(
                    icon='images/icon.png',
                    name='No recent bookmarks found',
                    description='Try again later or add some bookmarks',
                    on_enter=HideWindowAction()
                ))
            
            # Add a back to menu item at the end
            items.append(ExtensionResultItem(
                icon='images/icon.png',
                name='← Back to Menu',
                description='Return to the main menu',
                on_enter=SetUserQueryAction(extension.preferences['pinboard_kw'])
            ))
            
            return RenderResultListAction(items)
        
        elif action == 'toggle_tag':
            tag = data.get('tag')
            is_selected = data.get('is_selected')
            
            # Toggle tag selection
            if is_selected:
                if tag in extension.selected_tags:
                    extension.selected_tags.remove(tag)
            else:
                if tag not in extension.selected_tags:
                    extension.selected_tags.append(tag)
            
            # Render the tag browser again instead of redirecting to a new query
            tags = extension.get_tags()
            
            if not tags:
                # No tags found or error occurred
                error_msg = extension.error_message or "Unknown error"
                return RenderResultListAction([
                    ExtensionResultItem(
                        icon='images/tag.png',
                        name='No tags found',
                        description=f'Error: {error_msg}. Try again later or check your token.',
                        on_enter=HideWindowAction()
                    )
                ])
            
            # Show all tags
            tag_items = []
            # Limit the number of results
            max_display = 50
            count_total = len(tags)
            
            for tag_item in tags[:max_display]:
                is_selected = tag_item['name'] in extension.selected_tags
                action_data = {
                    'action': 'toggle_tag',
                    'tag': tag_item['name'],
                    'is_selected': is_selected
                }
                
                tag_items.append(ExtensionResultItem(
                    icon='images/tag_selected.png' if is_selected else 'images/tag.png',
                    name=f"{'✓ ' if is_selected else ''}{tag_item['name']}",
                    description=f"{tag_item['count']} bookmarks",
                    on_enter=ExtensionCustomAction(action_data, keep_app_open=True)
                ))
            
            if count_total > max_display:
                tag_items.append(ExtensionResultItem(
                    icon='images/tag.png',
                    name=f"... and {count_total - max_display} more tags",
                    description="Type to filter results",
                    on_enter=HideWindowAction()
                ))
            
            # Add a back to menu item
            tag_items.append(ExtensionResultItem(
                icon='images/icon.png',
                name='← Back to Menu',
                description='Return to the main menu',
                on_enter=SetUserQueryAction(extension.preferences['pinboard_kw'])
            ))
            
            # Add a search with tags item if tags are selected
            if extension.selected_tags:
                tag_items.append(ExtensionResultItem(
                    icon='images/icon.png',
                    name='Search with Selected Tags',
                    description=f"Search bookmarks with tags: {', '.join(extension.selected_tags)}",
                    on_enter=ExtensionCustomAction({
                        'action': 'search_bookmarks',
                        'tags': extension.selected_tags
                    }, keep_app_open=True)
                ))
            
            return RenderResultListAction(tag_items)
        
        elif action == 'add_bookmark':
            # This would normally connect to the active browser to get URL
            # For this example, we'll just show a placeholder
            items.append(ExtensionResultItem(
                icon='images/icon.png',
                name='Add bookmark feature',
                description='This would add the current browser URL to Pinboard',
                on_enter=HideWindowAction()
            ))
            
            return RenderResultListAction(items)
        
        return RenderResultListAction([])


if __name__ == '__main__':
    PinboardExtension().run() 