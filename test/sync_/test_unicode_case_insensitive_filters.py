from test._async_compat import mark_sync_test

from neomodel import StringProperty, StructuredNode


class UnicodeFilterNode(StructuredNode):
    name = StringProperty(unique_index=True)


@mark_sync_test
def test_unicode_case_insensitive_filters():
    node = UnicodeFilterNode(name="Алиса Тест").save()
    UnicodeFilterNode(name="Other").save()

    assert UnicodeFilterNode.nodes.filter(name__iexact="алиса тест").get() == node
    assert UnicodeFilterNode.nodes.filter(name__icontains="лиса").get() == node
    assert UnicodeFilterNode.nodes.filter(name__istartswith="али").get() == node
    assert UnicodeFilterNode.nodes.filter(name__iendswith="еСТ").get() == node
    assert UnicodeFilterNode.nodes.filter(name__iregex="алиса.*").get() == node
