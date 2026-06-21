"""Legacy entry point.

Use scripts/build_knowledge_base.py so privacy and FDA guidance data stay separate.
"""


def main():
    print("Use one of these commands instead:")
    print("  python scripts/build_knowledge_base.py privacy")
    print("  python scripts/build_knowledge_base.py fda_guidance")
    print("  python scripts/build_knowledge_base.py afrisafe_frameworks")


if __name__ == "__main__":
    main()
