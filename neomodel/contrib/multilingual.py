#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .. import RelationshipTo, StructuredNode, StringProperty


class Language(StructuredNode):
    code = StringProperty(unique_index=True)
    name = StringProperty()

    @classmethod
    def get(cls, lang):
        if isinstance(lang, Language):
            return lang
        else:
            try:
                return _lang[str(lang)]
            except KeyError:
                raise ValueError("No such language: {0}".format(lang))


class Multilingual(object):
    languages = RelationshipTo("Language", "LANGUAGE")

    def __init__(self, *args, **kwargs):
        try:
            super(Multilingual, self).__init__(*args, **kwargs)
        except TypeError:
            super(Multilingual, self).__init__()

    def attach_language(self, lang):
        self.languages.connect(Language.get(lang))

    def detach_language(self, lang):
        self.languages.disconnect(Language.get(lang))

    def has_language(self, lang):
        return self.languages.is_connected(Language.get(lang))

_lang = {
    "ar": Language(code="ar", name=u"العربية", name_en="Arabic").save(),
    "bg": Language(code="bg", name=u"български език", name_en="Bulgarian").save(),
    "en": Language(code="en", name=u"english", name_en="English").save(),
    "es": Language(code="es", name=u"español", name_en="Spanish").save(),
    "fr": Language(code="fr", name=u"français", name_en="French").save(),
    "pl": Language(code="pl", name=u"język polski", name_en="Polish").save(),
    "ro": Language(code="ro", name=u"limba română", name_en="Romanian").save(),
}
