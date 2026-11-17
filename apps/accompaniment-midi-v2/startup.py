"""Lightweight local-instance discovery, before importing Gradio."""
import json
import os
import urllib.request
import webbrowser

TITLE = 'STEM / MIDI Studio · 四大件'


def configure_ports():
    os.environ.setdefault('GRADIO_SERVER_PORT', '7861')
    os.environ.setdefault('GRADIO_NUM_PORTS', '20')


def find_existing():
    configure_ports()
    base = int(os.environ['GRADIO_SERVER_PORT'])
    count = int(os.environ['GRADIO_NUM_PORTS'])
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for port in range(base, min(base + count, 65536)):
        url = f'http://127.0.0.1:{port}'
        try:
            with opener.open(url + '/config', timeout=.5) as response:
                config = json.load(response)
            if config.get('title') == TITLE:
                return url
        except (OSError, ValueError):
            continue
    return None


def open_existing():
    url = find_existing()
    if url:
        print(f'V2 is already running. Opening {url}', flush=True)
        if not webbrowser.open(url):
            print(f'Open this address in your browser: {url}', flush=True)
        return True
    return False
