#!/usr/bin/env python3
"""Encode existing approved scene frames; no invented app interactions or audio."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import tempfile
from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('spec', help='JSON path relative to the campaign root')
    parser.add_argument('--replace', action='store_true', help='Replace the designated output; never use for a locked approved asset')
    args = parser.parse_args()
    root = args.root.resolve()

    def local(name):
        result = (root / name).resolve()
        if result == root or not result.is_relative_to(root):
            raise ValueError('Path outside campaign: ' + name)
        return result

    spec = json.loads(local(args.spec).read_text())
    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    if not ffmpeg or not ffprobe:
        raise RuntimeError('FFmpeg and ffprobe must be on PATH')
    output = local(spec['output'])
    if output.exists() and not args.replace:
        raise FileExistsError('Output exists; use a new version path or --replace for an authorized revision')
    if spec.get('approvedHashes'):
        locks = json.loads(local(spec['approvedHashes']).read_text())
        if spec['output'] in locks:
            raise ValueError('Refusing to overwrite a locked approved Reel')
    scenes = spec['scenes']
    width, height, fps = spec.get('width', 1080), spec.get('height', 1920), spec.get('fps', 30)
    transition = float(spec.get('transition', 0.4))
    zoom = float(spec.get('zoom', 0.025))
    if not scenes or width % 2 or height % 2 or fps <= 0 or not 0 < transition <= 1 or not 0 <= zoom <= .1:
        raise ValueError('Invalid scenes, even dimensions, fps, transition, or zoom')
    command = [ffmpeg, '-v', 'error', '-y', '-filter_complex_threads', '1']
    filters = []
    for index, scene in enumerate(scenes):
        duration = float(scene['seconds'])
        if duration <= 2 * transition:
            raise ValueError('Each scene must last longer than twice the transition')
        frame = local(scene['file'])
        with Image.open(frame) as image:
            if image.size != (width, height):
                raise ValueError('Scene dimensions do not match output: ' + scene['file'])
        command += ['-loop', '1', '-framerate', str(fps), '-t', str(duration), '-i', str(frame)]
        filters.append(f"[{index}:v]scale={width*2}:{height*2}:out_color_matrix=bt709:out_range=tv,format=yuv420p,zoompan=z='1+{zoom}*on/{max(1,round(duration*fps)-1)}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={width}x{height}:fps={fps},trim=duration={duration},setpts=PTS-STARTPTS[v{index}]")
    total = sum(float(s['seconds']) for s in scenes) - transition * (len(scenes) - 1)
    previous, offset = 'v0', float(scenes[0]['seconds']) - transition
    for index in range(1, len(scenes)):
        current = f'x{index}'
        filters.append(f'[{previous}][v{index}]xfade=transition=fade:duration={transition}:offset={offset}[{current}]')
        previous, offset = current, offset + float(scenes[index]['seconds']) - transition
    filters.append(f'[{previous}]setsar=1,setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709[out]')
    if spec.get('audio'):
        command += ['-stream_loop', '-1', '-i', str(local(spec['audio']))]
        filters.append(f'[{len(scenes)}:a]atrim=duration={total},afade=t=in:d=0.4,afade=t=out:st={max(0,total-1)}:d=1[audio]')
    command += ['-filter_complex', ';'.join(filters), '-map', '[out]']
    command += ['-map', '[audio]', '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', '-ac', '2'] if spec.get('audio') else ['-an']
    command += ['-t', str(total), '-r', str(fps), '-c:v', 'libx264', '-preset', 'fast', '-crf', '19', '-threads', '3', '-pix_fmt', 'yuv420p', '-x264-params', 'colorprim=bt709:transfer=bt709:colormatrix=bt709', '-movflags', '+faststart']
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='reel-', dir=output.parent) as temporary:
        video = Path(temporary) / 'reel.mp4'
        subprocess.run(command + [str(video)], check=True)
        subprocess.run([ffmpeg, '-v', 'error', '-i', str(video), '-f', 'null', '-'], check=True)
        metadata = json.loads(subprocess.check_output([ffprobe, '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(video)], text=True))
        video.replace(output)
    report = {'output': spec['output'], 'duration': total, 'decode': 'passed', 'metadata': metadata,
              'evidence': 'Technical encoding/decode only; inspect timing, appearance, playback, and audio separately.'}
    output.with_suffix('.verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'output': str(output), 'seconds': total, 'decode': 'passed'}))


if __name__ == '__main__':
    main()
