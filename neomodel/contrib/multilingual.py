from ..core import StructuredNode
from ..properties import StringProperty


class Language(StructuredNode):
    code = StringProperty(unique_index=True)


class Multilingual(object):

    def __init__(self, *args, **kwargs):
        try:
            super(Multilingual, self).__init__(*args, **kwargs)
        except TypeError:
            super(Multilingual, self).__init__()
        self.__parent__ = None
        for key, value in kwargs.iteritems():
            if key == "__parent__":
                self.__parent__ = value

    def attach_language(self, lang):
        if isinstance(self, StructuredNode):
            lang = Language(code=lang)
            self.__node__.get_or_create_path(("LANGUAGE", lang.__node__))

    def detach_language(self, lang):
        if isinstance(self, StructuredNode):
            lang = Language(code=lang)
            rels = self.__node__.get_relationships_with(lang.__node__, 1, "LANGUAGE")
            self.client.delete(*rels)

    def has_language(self, lang):
        pass
