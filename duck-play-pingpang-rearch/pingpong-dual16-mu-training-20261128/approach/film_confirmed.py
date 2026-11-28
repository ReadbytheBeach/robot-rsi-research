"""Render each 50 Hz scored frame of a selected high-friction crossing."""
from pathlib import Path
from unittest.mock import patch
import argparse,os,subprocess,sys
from search import HERE,SHORT
sys.path.insert(0,str(SHORT/'media'))
import film
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('folder');ap.add_argument('title');ap.add_argument('--primary',action='store_true');a=ap.parse_args()
    path=HERE/a.folder
    src=path/'trajectory.npz';out=path/'original-speed.partial.mp4'
    with patch.object(film,'ROOT',HERE):
        film.encode(src,out,a.title,fixed_grid=not a.primary,rate=50.)
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(out),'-f','null','-'],check=True)
    (out.with_suffix('.json')).replace(path/'original-speed.json')
    out.replace(path/'original-speed.mp4')
