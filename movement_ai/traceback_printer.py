import traceback, sys

def print_traceback():
    exc_type, exc_value, exc_traceback = sys.exc_info()
    print("".join(
        traceback.format_exception(exc_type, exc_value, exc_traceback)), file=sys.stderr)
