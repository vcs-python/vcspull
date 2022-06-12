import os

from libvcs.sync.git import GitRemote
from vcspull.types import ConfigDict

config_dict = {
    "/home/me/myproject/study/": {
        "linux": "git+git://git.kernel.org/linux/torvalds/linux.git",
        "freebsd": "git+https://github.com/freebsd/freebsd.git",
        "sphinx": "hg+https://bitbucket.org/birkenfeld/sphinx",
        "docutils": "svn+http://svn.code.sf.net/p/docutils/code/trunk",
    },
    "/home/me/myproject/github_projects/": {
        "kaptan": {
            "url": "git+git@github.com:tony/kaptan.git",
            "remotes": {
                "upstream": "git+https://github.com/emre/kaptan",
                "ms": "git+https://github.com/ms/kaptan.git",
            },
        }
    },
    "/home/me/myproject": {
        ".vim": {
            "url": "git+git@github.com:tony/vim-config.git",
            "shell_command_after": "ln -sf /home/me/.vim/.vimrc /home/me/.vimrc",
        },
        ".tmux": {
            "url": "git+git@github.com:tony/tmux-config.git",
            "shell_command_after": [
                "ln -sf /home/me/.tmux/.tmux.conf /home/me/.tmux.conf"
            ],
        },
    },
}

config_dict_expanded: list[ConfigDict] = [
    {
        "vcs": "git",
        "name": "linux",
        "dir": os.path.join("/home/me/myproject/study/", "linux"),
        "url": "git+git://git.kernel.org/linux/torvalds/linux.git",
    },
    {
        "vcs": "git",
        "name": "freebsd",
        "dir": os.path.join("/home/me/myproject/study/", "freebsd"),
        "url": "git+https://github.com/freebsd/freebsd.git",
    },
    {
        "vcs": "git",
        "name": "sphinx",
        "dir": os.path.join("/home/me/myproject/study/", "sphinx"),
        "url": "hg+https://bitbucket.org/birkenfeld/sphinx",
    },
    {
        "vcs": "git",
        "name": "docutils",
        "dir": os.path.join("/home/me/myproject/study/", "docutils"),
        "url": "svn+http://svn.code.sf.net/p/docutils/code/trunk",
    },
    {
        "vcs": "git",
        "name": "kaptan",
        "url": "git+git@github.com:tony/kaptan.git",
        "dir": os.path.join("/home/me/myproject/github_projects/", "kaptan"),
        "remotes": {
            "upstream": GitRemote(
                **{
                    "name": "upstream",
                    "fetch_url": "git+https://github.com/emre/kaptan",
                    "push_url": "git+https://github.com/emre/kaptan",
                }
            ),
            "ms": GitRemote(
                **{
                    "name": "ms",
                    "fetch_url": "git+https://github.com/ms/kaptan.git",
                    "push_url": "git+https://github.com/ms/kaptan.git",
                }
            ),
        },
    },
    {
        "vcs": "git",
        "name": ".vim",
        "dir": os.path.join("/home/me/myproject", ".vim"),
        "url": "git+git@github.com:tony/vim-config.git",
        "shell_command_after": ["ln -sf /home/me/.vim/.vimrc /home/me/.vimrc"],
    },
    {
        "vcs": "git",
        "name": ".tmux",
        "dir": os.path.join("/home/me/myproject", ".tmux"),
        "url": "git+git@github.com:tony/tmux-config.git",
        "shell_command_after": ["ln -sf /home/me/.tmux/.tmux.conf /home/me/.tmux.conf"],
    },
]
