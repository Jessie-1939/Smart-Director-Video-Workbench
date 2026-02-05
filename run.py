import sys
import os

# Add 'src' to python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

from src.main import main

if __name__ == "__main__":
    main()
