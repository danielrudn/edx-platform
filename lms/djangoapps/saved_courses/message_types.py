"""
ACE message types for the saved_courses module.
"""


from openedx.core.djangoapps.ace_common.message import BaseMessageType


class SaveForLater(BaseMessageType):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.options['transactional'] = True
