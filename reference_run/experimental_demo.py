"""Open the explicitly selected local research candidates; never overwrite stable weights."""
import json
from pathlib import Path
import sys

from project_io import HERE,digest


def main():
    base=HERE.parent/'outputs/autonomous-20261026/started-1248'
    try:
        for kind,flag in [('generation','--generation-checkpoint'),('photo','--photo-checkpoint')]:
            record=json.loads((base/(kind+'-selection.json')).read_text(encoding='utf-8'))['selected']
            path=Path(record['checkpoint']).resolve()
            if not path.is_relative_to(HERE.parent) or digest(path)!=record['checkpoint_sha256']:
                raise ValueError('实验权重路径或校验值不匹配')
            sys.argv.extend([flag,str(path)])
    except (OSError,ValueError,KeyError) as error:
        import tkinter as tk
        from tkinter import messagebox
        root=tk.Tk();root.withdraw()
        messagebox.showerror('实验模型暂不可用','本机实验权重不存在或校验失败。克隆源码不包含这些权重。\n请查看 ../docs/EXPERIMENTS.md；稳定发布包仍可单独使用。\n\n'+str(error),parent=root)
        root.destroy();return 1
    from gui import main as gui_main
    gui_main();return 0


if __name__=='__main__':raise SystemExit(main())
