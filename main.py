import json
import logging
import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any

from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent, ItemEnterEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction
from ulauncher.api.shared.action.HideWindowAction import HideWindowAction

logger = logging.getLogger(__name__)

class DockerWorkspaceExtension(Extension):
    def __init__(self):
        super().__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
        self.subscribe(ItemEnterEvent, ItemEnterEventListener())

def find_matching_dirs(query: str) -> List[Path]:
    """Find directories matching the query under HOME directory."""
    home = Path.home()
    query = query.lower()
    matches = []
    
    try:
        for root, dirs, _ in os.walk(str(home)):
            root_path = Path(root)
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for dir_name in dirs:
                if query in dir_name.lower():
                    full_path = root_path / dir_name
                    matches.append(full_path)
                    
                    # Limit results for performance
                    if len(matches) >= 5:
                        return matches
    except Exception as e:
        logger.error(f"Error searching directories: {e}")
        
    return matches

class KeywordQueryEventListener(EventListener):
    def on_event(self, event: KeywordQueryEvent, extension: DockerWorkspaceExtension) -> RenderResultListAction:
        query = event.get_argument() or ""
        items = []

        if not query:
            # Show default option to create new directory
            items.append(ExtensionResultItem(
                icon='images/icon.png',
                name="Enter directory path",
                description="Start typing to search or create a directory",
                on_enter=HideWindowAction()
            ))
            return RenderResultListAction(items)

        # Find matching directories
        matching_dirs = find_matching_dirs(query)
        
        # Add option to create new directory if it doesn't exist
        items.append(ExtensionResultItem(
            icon='images/icon.png',
            name=f"Create and use: {query}",
            description="Create this directory and use it as workspace",
            on_enter=ExtensionCustomAction({
                'action': 'create',
                'path': query
            }, keep_app_open=False)
        ))

        # Add existing directory matches
        for dir_path in matching_dirs:
            items.append(ExtensionResultItem(
                icon='images/icon.png',
                name=str(dir_path),
                description="Use this directory as workspace",
                on_enter=ExtensionCustomAction({
                    'action': 'use',
                    'path': str(dir_path)
                }, keep_app_open=False)
            ))

        return RenderResultListAction(items)

class ItemEnterEventListener(EventListener):
    def on_event(self, event: ItemEnterEvent, extension: DockerWorkspaceExtension) -> HideWindowAction:
        data = event.get_data()
        workspace_path = Path(data['path'])

        if data['action'] == 'create':
            # Create directory if it doesn't exist
            try:
                workspace_path = Path.home() / workspace_path
                workspace_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"Failed to create directory: {e}")
                return HideWindowAction()

        # Get the Docker command template and replace workspace
        docker_cmd = extension.preferences['docker_command']
        docker_cmd = docker_cmd.replace('$WORKSPACE_BASE', str(workspace_path))

        try:
            # Execute in Kitty terminal
            subprocess.Popen(['kitty', '--', 'bash', '-c', f'{docker_cmd}; read -p "Press Enter to close..."'])
        except Exception as e:
            logger.error(f"Failed to execute command: {e}")

        return HideWindowAction()

if __name__ == '__main__':
    DockerWorkspaceExtension().run()
