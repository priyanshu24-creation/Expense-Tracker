class IgnoreBrokenPipeFilter:
    def filter(self, record):
        message = record.getMessage()
        return "Broken pipe" not in message
