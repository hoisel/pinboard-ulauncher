import json
import urllib.request
import urllib.parse
import urllib.error
import logging
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
from ulauncher.api.shared.action.DoNothingAction import DoNothingAction
from ulauncher.api.shared.action.CopyToClipboardAction import CopyToClipboardAction


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
        self.current_tag_filter = ""  # Armazenar o filtro de tags atual
        self.reset_query_requested = False  # Nova flag para indicar que queremos resetar a query
        
        # Setup logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def get_token(self):
        return self.preferences.get('pinboard_token', '')

    def get_bookmarks(self, tag=''):
        """Get bookmarks from Pinboard API"""
        if not self.get_token():
            return []
            
        # Use cache if available and not expired
        cache_key = f'bookmarks_{tag}'
        current_time = datetime.now()
        cache_time_minutes = int(self.preferences.get('cache_time', '5'))
        cache_time_seconds = cache_time_minutes * 60
        
        if (self.last_cache_time and 
            (current_time - self.last_cache_time).total_seconds() < cache_time_seconds and
            cache_key in self.cache):
            return self.cache[cache_key]
            
        # Not in cache, fetch from API
        self.logger.info(f"Cache miss for bookmarks, tag: {tag or 'all'}")
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
            
        # Use cache if available and not expired
        cache_key = 'recent_bookmarks'
        current_time = datetime.now()
        cache_time_minutes = int(self.preferences.get('cache_time', '5'))
        cache_time_seconds = cache_time_minutes * 60
        
        if (self.last_cache_time and 
            (current_time - self.last_cache_time).total_seconds() < cache_time_seconds and
            cache_key in self.cache):
            return self.cache[cache_key]
            
        # Not in cache, fetch from API
        self.logger.info(f"Cache miss for recent bookmarks, count: {count}")
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
            
        # Use cache if available and not expired
        cache_key = 'tags'
        current_time = datetime.now()
        cache_time_minutes = int(self.preferences.get('cache_time', '5'))
        cache_time_seconds = cache_time_minutes * 60
        
        if (self.last_cache_time and 
            (current_time - self.last_cache_time).total_seconds() < cache_time_seconds and
            cache_key in self.cache):
            return self.cache[cache_key]
            
        # Not in cache, fetch from API
        self.logger.info("Cache miss for tags")
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

        self.logger.info(f"Adding bookmark: {title} ({url})")
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
                    icon='images/pinboard.png',
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
                icon='images/search.png',
                name='Search Bookmarks',
                description=search_description,
                on_enter=ExtensionCustomAction({
                    'action': 'search_bookmarks',
                    'tags': extension.selected_tags
                }, keep_app_open=True)
            ))

                     # Clear selected tags item (se houver tags selecionadas)
            if extension.selected_tags:
                items.append(ExtensionResultItem(
                    icon='images/clear.png',
                    name='Clear Selected Tags',
                    description=f"Currently selected: {', '.join(extension.selected_tags)}",
                    on_enter=ExtensionCustomAction({
                        'action': 'clear_tags'
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
                icon='images/clock.png',
                name='Browse Recent Bookmarks',
                description='View your most recent Pinboard bookmarks',
                on_enter=ExtensionCustomAction({
                    'action': 'browse_recent'
                }, keep_app_open=True)
            ))
            
            # Add new bookmark item
            items.append(ExtensionResultItem(
                icon='images/plus.png',
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
            
            # Se há uma solicitação para resetar a query, faça isso e resete a flag
            if extension.reset_query_requested and query != "#":
                extension.reset_query_requested = False
                return SetUserQueryAction(f"{extension.preferences['pinboard_kw']} #")
            
            # Filter tags by query
            tag_query = query[1:].lower().strip()
            extension.current_tag_filter = tag_query  # Salvar o filtro atual
            filtered_tags = tags
            
            if tag_query:
                filtered_tags = [tag for tag in tags if tag_query in tag['name'].lower()]
            
            
            # Add a back to menu item 
            items.insert(0, ExtensionResultItem(
                icon='images/back.png',
                name='Back to Menu',
                description='Return to the main menu',
                on_enter=SetUserQueryAction(extension.preferences['pinboard_kw'])
            ))
            
            # Separar tags selecionadas e não selecionadas
            selected_tags = []
            unselected_tags = []
            
            for tag in filtered_tags:
                if tag['name'] in extension.selected_tags:
                    selected_tags.append(tag)
                else:
                    unselected_tags.append(tag)
            
            # Add a search with tags item if tags are selected
            if extension.selected_tags:
                
                # Adicionar opção para limpar todas as tags selecionadas
                items.insert(1, ExtensionResultItem(
                    icon='images/clear.png',
                    name='Clear All Selected Tags',
                    description=f"Currently selected: {', '.join(extension.selected_tags)}",
                    on_enter=ExtensionCustomAction({
                        'action': 'clear_tags'
                    }, keep_app_open=True)
                ))
            
            # Exibir tags selecionadas primeiro
            for tag in selected_tags:
                action_data = {
                    'action': 'toggle_tag',
                    'tag': tag['name'],
                    'is_selected': True
                }
                
                items.append(ExtensionResultItem(
                    icon='images/tag_selected.png',
                    name=f"{tag['name']}",
                    description=f"{tag['count']} bookmarks (Click to deselect)",
                    on_enter=ExtensionCustomAction(action_data, keep_app_open=True)
                ))
            
            # Depois exibir tags não selecionadas
            # Limit the number of results
            max_results = int(extension.preferences.get('max_results', '50'))
            max_display = max_results - len(selected_tags)  # Ajustar limite considerando tags selecionadas
            count_total = len(unselected_tags)
            
            for tag in unselected_tags[:max_display]:
                action_data = {
                    'action': 'toggle_tag',
                    'tag': tag['name'],
                    'is_selected': False
                }
                
                items.append(ExtensionResultItem(
                    icon='images/tag.png',
                    name=f"{tag['name']}",
                    description=f"{tag['count']} bookmarks (Click to select)",
                    on_enter=ExtensionCustomAction(action_data, keep_app_open=True)
                ))
            
            if count_total > max_display:
                items.append(ExtensionResultItem(
                    icon='images/tag.png',
                    name=f"... and {count_total - max_display} more tags",
                    description="Update max results to see more tags",
                    on_enter=HideWindowAction()
                ))
            
            if len(items) <= 2:  # Apenas os itens de view e back
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
                    icon='images/pinboard.png',
                    name=bookmark.get('description', 'No title'),
                    description=bookmark.get('href', 'No URL'),
                    on_enter=OpenUrlAction(bookmark.get('href', ''))
                ))
            
            if len(items) <= 2:  # Apenas os itens de view e back
                # Check if there was an error
                if extension.error_message:
                    error_item = ExtensionResultItem(
                        icon='images/pinboard.png',
                        name='Error loading recent bookmarks',
                        description=f'Error: {extension.error_message}',
                        on_enter=HideWindowAction()
                    )
                    items.append(error_item)
                else:
                    items.append(ExtensionResultItem(
                        icon='images/pinboard.png',
                        name='No matching recent bookmarks found',
                        description='Try a different search term',
                        on_enter=HideWindowAction()
                    ))
            
            # Adicionar o item representativo da view atual como primeiro item
            items.insert(0, ExtensionResultItem(
                icon='images/info.png',
                name='Browsing Recent Bookmarks',
                description=f"{'Currently viewing all recent bookmarks' if not query else f'Filtering recent bookmarks: {query}'}",
                on_enter=HideWindowAction()
            ))
            
            # Add a back to menu item
            items.insert(1, ExtensionResultItem(
                icon='images/back.png',
                name='Back to Menu',
                description='Return to the main menu',
                on_enter=SetUserQueryAction(extension.preferences['pinboard_kw'])
            ))

            return RenderResultListAction(items)
        
        # Default: Search bookmarks (normal search mode)
        extension.current_view = 'search'
        
        # Adicionar o item representativo da view atual como primeiro item
        search_description = "Search all bookmarks"
        if extension.selected_tags:
            search_description = f"Filtering by tags: {', '.join(extension.selected_tags)}"
            
        items.append(ExtensionResultItem(
            icon='images/search.png',
            name='Search Bookmarks',
            description=search_description,
            on_enter=HideWindowAction()
        ))
        
        # Add a back to menu item
        items.append(ExtensionResultItem(
            icon='images/back.png',
            name='Back to Menu',
            description='Return to the main menu',
            on_enter=SetUserQueryAction(extension.preferences['pinboard_kw'])
        ))
        
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
                icon='images/pinboard.png',
                name=bookmark.get('description', 'No title'),
                description=bookmark.get('href', 'No URL'),
                on_enter=OpenUrlAction(bookmark.get('href', ''))
            ))
            
            # Limit number of results
            max_results = int(extension.preferences.get('max_results', '50'))
            if len(items) - 2 >= max_results:  # -2 para considerar os itens de cabeçalho
                items.append(ExtensionResultItem(
                    icon='images/info.png',
                    name=f'...and more results',
                    description=f'Your search returned more than {max_results} results',
                ))
                break
        
        if len(items) <= 2:  # Apenas os itens de view e back
            # Check if there was an error
            if extension.error_message:
                error_item = ExtensionResultItem(
                    icon='images/pinboard.png',
                    name='Error loading bookmarks',
                    description=f'Error: {extension.error_message}',
                    on_enter=HideWindowAction()
                )
                items.append(error_item)
            else:
                items.append(ExtensionResultItem(
                    icon='images/pinboard.png',
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
            
            # Adicionar o item representativo da view atual como primeiro item
            items.append(ExtensionResultItem(
                icon='images/info.png',
                name='Browsing Recent Bookmarks',
                description='Currently viewing your most recent bookmarks',
                on_enter=HideWindowAction()
            ))
            
            # Add a back to menu item
            items.append(ExtensionResultItem(
                icon='images/back.png',
                name='Back to Menu',
                description='Return to the main menu',
                on_enter=SetUserQueryAction(extension.preferences['pinboard_kw'])
            ))
            
            # Get recent bookmarks
            recent_bookmarks = extension.get_recent_bookmarks()

            if not recent_bookmarks and extension.error_message:
                # Show error
                items.append(ExtensionResultItem(
                    icon='images/pinboard.png',
                    name='Error loading recent bookmarks',
                    description=f'Error: {extension.error_message}',
                    on_enter=HideWindowAction()
                ))
                return RenderResultListAction(items)
            
            # Create result items for recent bookmarks
            for bookmark in recent_bookmarks:
                items.append(ExtensionResultItem(
                    icon='images/pinboard.png',
                    name=bookmark.get('description', 'No title'),
                    description=bookmark.get('href', 'No URL'),
                    on_enter=OpenUrlAction(bookmark.get('href', ''))
                ))
            
            if len(items) <= 2:  # Apenas os itens de view e back
                items.append(ExtensionResultItem(
                    icon='images/pinboard.png',
                    name='No recent bookmarks found',
                    description='Try again later or add some bookmarks',
                    on_enter=HideWindowAction()
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
            
            # Limpar o filtro de tags após selecionar uma tag
            extension.current_tag_filter = ""
            
            # Render the tag browser again
            tags = extension.get_tags()
            
            # Adicionar o item representativo da view atual como primeiro item
            tag_items = [
                ExtensionResultItem(
                    icon='images/back.png',
                    name='Back to Menu',
                    description=(f"Return to search bookmarks with tags: {', '.join(extension.selected_tags)}" if extension.selected_tags else ""),
                    on_enter=SetUserQueryAction(extension.preferences['pinboard_kw'])
                )
            ]
            
            # Add a search with tags item if tags are selected
            if extension.selected_tags:
                
                # Adicionar opção para limpar todas as tags selecionadas
                tag_items.insert(1, ExtensionResultItem(
                    icon='images/clear.png',
                    name='Clear All Selected Tags',
                    description=f"Currently selected: {', '.join(extension.selected_tags)}",
                    on_enter=ExtensionCustomAction({
                        'action': 'clear_tags'
                    }, keep_app_open=True)
                ))
            
            if not tags:
                # No tags found or error occurred
                error_msg = extension.error_message or "Unknown error"
                tag_items.append(ExtensionResultItem(
                    icon='images/tag.png',
                    name='No tags found',
                    description=f'Error: {error_msg}. Try again later or check your token.',
                    on_enter=HideWindowAction()
                ))
                return RenderResultListAction(tag_items)
            
            # Separar tags selecionadas e não selecionadas
            selected_tags = []
            unselected_tags = []
            
            for tag_item in tags:
                if tag_item['name'] in extension.selected_tags:
                    selected_tags.append(tag_item)
                else:
                    unselected_tags.append(tag_item)
            
            # Exibir tags selecionadas primeiro
            for tag_item in selected_tags:
                action_data = {
                    'action': 'toggle_tag',
                    'tag': tag_item['name'],
                    'is_selected': True
                }
                
                tag_items.append(ExtensionResultItem(
                    icon='images/tag_selected.png',
                    name=f"{tag_item['name']}",
                    description=f"{tag_item['count']} bookmarks (Click to deselect)",
                    on_enter=ExtensionCustomAction(action_data, keep_app_open=True)
                ))
            
            # Depois exibir tags não selecionadas
            max_results = int(extension.preferences.get('max_results', '50'))
            max_display = max_results - len(selected_tags)  # Ajustar limite considerando tags selecionadas
            count_total = len(unselected_tags)
            
            for tag_item in unselected_tags[:max_display]:
                action_data = {
                    'action': 'toggle_tag',
                    'tag': tag_item['name'],
                    'is_selected': False
                }
                
                tag_items.append(ExtensionResultItem(
                    icon='images/tag.png',
                    name=f"{tag_item['name']}",
                    description=f"{tag_item['count']} bookmarks (Click to select)",
                    on_enter=ExtensionCustomAction(action_data, keep_app_open=True)
                ))
            
            if count_total > max_display:
                tag_items.append(ExtensionResultItem(
                    icon='images/tag.png',
                    name=f"... and {count_total - max_display} more tags",
                    description="Update max results to see more tags",
                    on_enter=HideWindowAction()
                ))
            
            # O primeiro item (ícone de info) já tem a ação SetUserQueryAction para resetar a query para #
            return RenderResultListAction(tag_items)
        
        elif action == 'clear_tags':
            # Limpar todas as tags selecionadas
            extension.selected_tags = []
            
            # Limpar o filtro atual
            extension.current_tag_filter = ""
            
            # Se estamos na view de tags, renderizar diretamente todas as tags
            if extension.current_view == 'tags':
                tags = extension.get_tags()
                
                # Adicionar o item principal e botão de voltar
                tag_items = [
                    ExtensionResultItem(
                        icon='images/back.png',
                        name='Back to Menu',
                        description='Return to the main menu',
                        on_enter=SetUserQueryAction(extension.preferences['pinboard_kw'])
                    )
                ]
                
                # Exibir todas as tags
                max_results = int(extension.preferences.get('max_results', '50'))
                max_display = max_results
                count_total = len(tags)
                
                for tag_item in tags[:max_display]:
                    action_data = {
                        'action': 'toggle_tag',
                        'tag': tag_item['name'],
                        'is_selected': False
                    }
                    
                    tag_items.append(ExtensionResultItem(
                        icon='images/tag.png',
                        name=f"{tag_item['name']}",
                        description=f"{tag_item['count']} bookmarks (Click to select)",
                        on_enter=ExtensionCustomAction(action_data, keep_app_open=True)
                    ))
                
                if count_total > max_display:
                    tag_items.append(ExtensionResultItem(
                        icon='images/tag.png',
                        name=f"... and {count_total - max_display} more tags",
                        description="Update max results to see more tags",
                        on_enter=HideWindowAction()
                    ))
                
                return RenderResultListAction(tag_items)
            else:
                # Caso esteja na view principal, redirecionar para a view principal
                # diretamente em vez de mostrar uma tela de confirmação
                return SetUserQueryAction(extension.preferences['pinboard_kw'])
        
        elif action == 'add_bookmark':
            # This would normally connect to the active browser to get URL
            # For this example, we'll just show a placeholder
            items.append(ExtensionResultItem(
                icon='images/info.png',
                name='Adding New Bookmark',
                description='Currently in add bookmark mode',
                on_enter=HideWindowAction()
            ))
            
            items.append(ExtensionResultItem(
                icon='images/back.png',
                name='Back to Menu',
                description='Return to the main menu',
                on_enter=SetUserQueryAction(extension.preferences['pinboard_kw'])
            ))
            
            items.append(ExtensionResultItem(
                icon='images/pinboard.png',
                name='Add bookmark feature',
                description='This would add the current browser URL to Pinboard',
                on_enter=HideWindowAction()
            ))
            
            return RenderResultListAction(items)
        
        return RenderResultListAction([])


if __name__ == '__main__':
    PinboardExtension().run() 