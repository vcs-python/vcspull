import os

config_dict = {
    '/home/me/myproject/study/': {
        'linux': 'git+git://git.kernel.org/linux/torvalds/linux.git',
        'freebsd': 'git+https://github.com/freebsd/freebsd.git',
        'sphinx': 'hg+https://bitbucket.org/birkenfeld/sphinx',
        'docutils': 'svn+http://svn.code.sf.net/p/docutils/code/trunk',
    },
    '/home/me/myproject/github_projects/': {
        'kaptan': {
            'url': 'git+git@github.com:tony/kaptan.git',
            'remotes': {
                'upstream': 'git+https://github.com/emre/kaptan',
                'ms': 'git+https://github.com/ms/kaptan.git',
            },
        }
    },
    '/home/me/myproject': {
        '.vim': {
            'url': 'git+git@github.com:tony/vim-config.git',
            'shell_command_after': 'ln -sf /home/me/.vim/.vimrc /home/me/.vimrc',
        },
        '.tmux': {
            'url': 'git+git@github.com:tony/tmux-config.git',
            'shell_command_after': [
                'ln -sf /home/me/.tmux/.tmux.conf /home/me/.tmux.conf'
            ],
        },
    },
}

config_dict_expanded = [
    {
        'name': 'linux',
        'parent_dir': '/home/me/myproject/study/',
        'repo_dir': os.path.join('/home/me/myproject/study/', 'linux'),
        'url': 'git+git://git.kernel.org/linux/torvalds/linux.git',
    },
    {
        'name': 'freebsd',
        'parent_dir': '/home/me/myproject/study/',
        'repo_dir': os.path.join('/home/me/myproject/study/', 'freebsd'),
        'url': 'git+https://github.com/freebsd/freebsd.git',
    },
    {
        'name': 'sphinx',
        'parent_dir': '/home/me/myproject/study/',
        'repo_dir': os.path.join('/home/me/myproject/study/', 'sphinx'),
        'url': 'hg+https://bitbucket.org/birkenfeld/sphinx',
    },
    {
        'name': 'docutils',
        'parent_dir': '/home/me/myproject/study/',
        'repo_dir': os.path.join('/home/me/myproject/study/', 'docutils'),
        'url': 'svn+http://svn.code.sf.net/p/docutils/code/trunk',
    },
    {
        'name': 'kaptan',
        'url': 'git+git@github.com:tony/kaptan.git',
        'parent_dir': '/home/me/myproject/github_projects/',
        'repo_dir': os.path.join('/home/me/myproject/github_projects/', 'kaptan'),
        'remotes': [
            {'remote_name': 'upstream', 'url': 'git+https://github.com/emre/kaptan'},
            {'remote_name': 'ms', 'url': 'git+https://github.com/ms/kaptan.git'},
        ],
    },
    {
        'name': '.vim',
        'parent_dir': '/home/me/myproject',
        'repo_dir': os.path.join('/home/me/myproject', '.vim'),
        'url': 'git+git@github.com:tony/vim-config.git',
        'shell_command_after': ['ln -sf /home/me/.vim/.vimrc /home/me/.vimrc'],
    },
    {
        'name': '.tmux',
        'parent_dir': '/home/me/myproject',
        'repo_dir': os.path.join('/home/me/myproject', '.tmux'),
        'url': 'git+git@github.com:tony/tmux-config.git',
        'shell_command_after': ['ln -sf /home/me/.tmux/.tmux.conf /home/me/.tmux.conf'],
    },
]
