import logging,re

class CallbackLogFilter(logging.Filter):
    """Redact authorization codes/nonces before Django's request logger emits them."""
    def filter(self,record):
        message=record.getMessage()
        if '/integrations/google/callback/' in message:
            record.msg=re.sub(r'([?&](?:code|state|error_description)=)[^&\s"]+',r'\1[redacted]',message)
            record.args=()
        return True
