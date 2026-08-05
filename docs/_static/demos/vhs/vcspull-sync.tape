Output docs/_static/demos/vhs/vcspull-sync.gif
Output docs/_static/demos/vhs/vcspull-sync.mp4
Output docs/_static/demos/vhs/vcspull-sync.webm

Set Shell "bash"
Set FontSize 18
Set Theme "Catppuccin Mocha"
Set TypingSpeed 50ms
Set Padding 20
Set Width 1400
Set Height 212

# Wait syncs to the prompt returning, so the demo advances when the command
# actually finishes instead of after a guessed Sleep.
Set WaitPattern /[$#>]\s*$/
Set WaitTimeout 90s

# The sandbox from docs/_static/demos/setup-sandbox.sh. Redirecting HOME keeps real paths
# off screen: everything renders as ~/code/... instead of a developer's layout.
Env HOME "/tmp/vcspull-demo"
Env XDG_CONFIG_HOME "/tmp/vcspull-demo/.config"
Env PATH "/tmp/vcspull-demo/bin:/usr/local/bin:/usr/bin:/bin"

Hide
Type "cd ~ && rm -rf ~/code && clear"
Enter
Show

Type "vcspull sync -w ~/code/python --all"
Enter
Wait
Sleep 2s
