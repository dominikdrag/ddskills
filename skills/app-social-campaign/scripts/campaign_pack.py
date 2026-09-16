#!/usr/bin/env python3
"""Build a local campaign review board and an explicit-file delivery archive."""
from pathlib import Path
from html import escape
from urllib.parse import quote
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import zipfile
from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('manifest', help='Campaign JSON path relative to root')
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--zip', action='store_true', help='Package only a campaign whose listed posts are ready')
    args = parser.parse_args()
    root = args.root.resolve()

    def local(name):
        result = (root / name).resolve()
        if result == root or not result.is_relative_to(root):
            raise ValueError('Path outside campaign: ' + name)
        return result

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def url(name):
        local(name)
        return quote(name, safe='/')

    data = json.loads(local(args.manifest).read_text())
    if data.get('schema_version') != 1 or not data.get('posts'):
        raise ValueError('Expected schema_version 1 and nonempty posts')
    ids = [p['id'] for p in data['posts']]
    if len(ids) != len(set(ids)) or any(not re.fullmatch(r'[a-zA-Z0-9_-]+', p) for p in ids):
        raise ValueError('Post IDs must be unique safe directory names')
    if args.zip and any(p.get('status') != 'ready' for p in data['posts']):
        raise ValueError('ZIP delivery requires every listed post to be ready; narrow to the finished sample or finish production')
    files = {args.manifest}
    checks = []
    for name in data.get('extra_files', []) + [d['file'] for d in data.get('documents', [])]:
        if not local(name).is_file():
            raise FileNotFoundError(name)
        files.add(name)
    if data.get('approved_hashes'):
        name = data['approved_hashes']
        files.add(name)
        for file, expected in json.loads(local(name).read_text()).items():
            if sha(local(file)) != expected:
                raise ValueError('Approved file changed: ' + file)

    for post in data['posts']:
        if len(post['caption']) > data.get('caption_limit', 2200):
            raise ValueError('Caption exceeds configured limit: ' + post['id'])
        if post.get('status') == 'ready' and not post.get('assets'):
            raise ValueError('Ready post has no main assets: ' + post['id'])
        if post.get('status') == 'ready' and post.get('format', '').lower() in ('reel', 'video'):
            if not any(asset.get('type') == 'video' for asset in post.get('assets', [])):
                raise ValueError('Ready Reel requires an actual video asset: ' + post['id'])
        for asset in post.get('assets', []) + post.get('stories', []):
            file = local(asset['file'])
            if not file.is_file() or not asset.get('alt'):
                raise ValueError('Missing asset or accessible description: ' + asset['file'])
            files.add(asset['file'])
            if asset.get('poster'):
                if not local(asset['poster']).is_file():
                    raise FileNotFoundError(asset['poster'])
                files.add(asset['poster'])
            if asset['type'] == 'image':
                with Image.open(file) as image:
                    image.load()
                    if image.size != (asset['width'], asset['height']) or image.mode != 'RGB':
                        raise ValueError('Image dimensions/RGB mismatch: ' + asset['file'])
                checks.append({'file': asset['file'], 'imageDimensionsRGB': 'passed'})
            elif asset['type'] == 'video':
                ffprobe = shutil.which('ffprobe')
                if not ffprobe:
                    raise RuntimeError('ffprobe is needed to validate video metadata')
                metadata = json.loads(subprocess.check_output([ffprobe, '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(file)], text=True))
                stream = next(s for s in metadata['streams'] if s['codec_type'] == 'video')
                if (stream['width'], stream['height']) != (asset['width'], asset['height']):
                    raise ValueError('Video dimensions mismatch: ' + asset['file'])
                checks.append({'file': asset['file'], 'metadata': 'passed', 'codec': stream['codec_name'], 'duration': metadata['format']['duration']})
            else:
                raise ValueError('Unknown asset type: ' + asset['type'])
    if args.check_only:
        print(json.dumps({'posts': len(ids), 'assets': len(checks), 'checks': 'passed', 'evidence': 'Technical metadata and file checks only.'}))
        return

    def write(name, content):
        output = local(name)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content)
        files.add(name)

    def media(asset):
        label = escape(asset.get('role', asset['type']))
        description = escape(asset['alt'])
        src = url(asset['file'])
        if asset['type'] == 'video':
            poster = f' poster="{url(asset["poster"])}"' if asset.get('poster') else ''
            return f'<figure><video controls playsinline preload="metadata"{poster} src="{src}" aria-label="{description}"></video><figcaption>{label} · <a href="{src}" download>Download MP4</a><details><summary>Video description</summary><p>{description}</p></details></figcaption></figure>'
        return f'<figure><button class="zoom" data-src="{src}"><img src="{src}" alt="{description}"></button><figcaption>{label} · <a href="{src}" download>Download image</a></figcaption></figure>'

    cards, order = [], ['# Publishing order\n', data.get('release_note', ''), '\n']
    for post in data['posts']:
        folder = 'posts/' + post['id']
        write(folder + '/caption.txt', post['caption'] + '\n')
        write(folder + '/alt-text.txt', '\n\n'.join(a['file'] + ' — ' + a['alt'] for a in post.get('assets', []) + post.get('stories', [])) + '\n')
        order.append(f"## {post['id']} — {post['title']}\n\n{post.get('day', 'Unscheduled')} · {post.get('format', '')} · {post.get('status', 'planned')}\n\n" + '\n'.join('- ' + a.get('role', a['type']) + ': ' + a['file'] for a in post.get('assets', [])) + '\n\nCaption: ' + folder + '/caption.txt\n\n' + post.get('publication_note', '') + '\n')
        stories = '<details><summary>Supporting Stories</summary><div class="rail">' + ''.join(media(a) for a in post.get('stories', [])) + '</div></details>' if post.get('stories') else ''
        cards.append(f'<article data-week="{escape(str(post.get("week", "")))}"><div class="label">{escape(post["id"])} · {escape(post.get("day", "Unscheduled"))} · {escape(post.get("status", "planned"))}</div><h2>{escape(post["title"])}</h2><p>{escape(post.get("goal", ""))}</p><div class="rail">' + ''.join(media(a) for a in post.get('assets', [])) + f'</div><details><summary>Caption</summary><pre>{escape(post["caption"])}</pre><button class="copy">Copy caption</button></details>{stories}<p class="note">{escape(post.get("publication_note", ""))}</p></article>')
    write('publishing-order.md', '\n'.join(order))
    colors = {key: data.get('brand', {}).get(key, default) for key, default in [('background', '#f7f5ef'), ('text', '#262922'), ('accent', '#637451')]}
    if any(not re.fullmatch(r'#[0-9A-Fa-f]{6}', value) for value in colors.values()):
        raise ValueError('Board colors must be six-digit hex values')
    weeks = list(dict.fromkeys(str(p['week']) for p in data['posts'] if 'week' in p))
    filters = '<button data-filter="all">All posts</button>' + ''.join(f'<button data-filter="{escape(w)}">Week {escape(w)}</button>' for w in weeks)
    docs = [{'label': 'Publishing order', 'file': 'publishing-order.md'}] + data.get('documents', [])
    nav = ' · '.join(f'<a href="{url(d["file"])}">{escape(d["label"])}</a>' for d in docs)
    css = 'body{margin:0;font:17px/1.5 system-ui;background:var(--bg);color:var(--ink)}main{max-width:1300px;margin:auto;padding:40px 24px}h1{font-size:clamp(36px,6vw,72px);line-height:1.05;max-width:1000px}h2{font-size:28px;line-height:1.2}a{color:inherit}button{font:inherit;cursor:pointer}nav,.filters{display:flex;gap:12px;flex-wrap:wrap;margin:28px 0}.filters button,.copy{padding:10px 16px;border:1px solid var(--accent);border-radius:30px;background:transparent;color:inherit}article{border-top:1px solid #8886;padding:34px 0}.label,.note,figcaption{font-size:14px}.rail{display:flex;gap:16px;overflow-x:auto;padding:12px 0}figure{margin:0;flex:0 0 min(300px,80vw)}img,video{width:100%;display:block;border-radius:8px}video{max-height:540px;background:#111}.zoom{padding:0;border:0;background:none;width:100%}pre{font:inherit;white-space:pre-wrap;overflow-wrap:anywhere;max-width:750px}summary{cursor:pointer;padding:12px 0}dialog{border:0;padding:12px;background:var(--bg);max-width:90vw}dialog img{width:auto;max-width:85vw;max-height:85vh}dialog button{display:block;margin:12px auto 0}dialog::backdrop{background:#000c}[hidden]{display:none!important}'
    js = "document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{document.querySelectorAll('article').forEach(a=>{a.hidden=b.dataset.filter!=='all'&&a.dataset.week!==b.dataset.filter;if(a.hidden)a.querySelectorAll('video').forEach(v=>v.pause())})});document.querySelectorAll('.copy').forEach(b=>b.onclick=async()=>{try{await navigator.clipboard.writeText(b.previousElementSibling.textContent);b.textContent='Copied'}catch(e){b.textContent='Select and copy the text above'}});const d=document.querySelector('dialog');document.querySelectorAll('.zoom').forEach(b=>b.onclick=()=>{d.querySelector('img').src=b.dataset.src;d.querySelector('img').alt=b.querySelector('img').alt;d.showModal()});d.querySelector('button').onclick=()=>d.close();document.querySelectorAll('video').forEach(v=>v.onplay=()=>document.querySelectorAll('video').forEach(other=>{if(other!==v)other.pause()}));"
    page = '<!doctype html><html lang="' + escape(data.get('language', 'en')) + '"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>' + escape(data['title']) + '</title><style>:root{--bg:' + colors['background'] + ';--ink:' + colors['text'] + ';--accent:' + colors['accent'] + '}' + css + '</style><body><main><div class="label">CAMPAIGN REVIEW · ' + escape(data.get('phase', 'draft')) + '</div><h1>' + escape(data['title']) + '</h1><p>' + escape(data.get('summary', '')) + '</p><p>' + escape(data.get('release_note', '')) + '</p><nav>' + nav + '</nav><div class="filters">' + filters + '</div>' + ''.join(cards) + '</main><dialog><img alt=""><button>Close</button></dialog><script>' + js + '</script></body></html>'
    write('review.html', page)
    write('technical-checks.json', json.dumps({'evidence': 'Files, dimensions, RGB, hashes, and metadata only. Inspect visuals and exercise browser controls separately.', 'checks': checks}, indent=2) + '\n')
    archive_path = root / 'campaign.zip'
    if args.zip:
        if any(local(name) == archive_path for name in files):
            raise ValueError('Archive cannot include itself')
        manifest = [{'file': name, 'bytes': local(name).stat().st_size, 'sha256': sha(local(name))} for name in sorted(files)]
        write('delivery-manifest.json', json.dumps(manifest, indent=2) + '\n')
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(files):
                archive.write(local(name), name)
        with zipfile.ZipFile(archive_path) as archive:
            if archive.testzip() is not None:
                raise ValueError('ZIP CRC failure')
            for item in manifest:
                if hashlib.sha256(archive.read(item['file'])).hexdigest() != item['sha256']:
                    raise ValueError('Archived hash mismatch: ' + item['file'])
    print(json.dumps({'posts': len(ids), 'assets': len(checks), 'board': str(root / 'review.html'), 'archive': str(archive_path) if args.zip else None}))


if __name__ == '__main__':
    main()
