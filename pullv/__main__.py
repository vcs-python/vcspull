import sys
import os


def run():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, base)
    import pullv
    pullv.main()

if __name__ == '__main__':
    exit = run()
    if exit:
        sys.exit(exit)
