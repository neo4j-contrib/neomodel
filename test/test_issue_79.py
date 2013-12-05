from neomodel import StructuredNode, StringProperty, RelationshipTo, RelationshipFrom


class Cell(StructuredNode):
    next_cell = RelationshipTo('Cell', 'NEXT_CELL') # This can point to multiple
    prev_cell = RelationshipFrom('Cell', 'NEXT_CELL')
    members = RelationshipFrom('CellMember', 'CONTAINED_BY')


class CellMember(StructuredNode):
    containing_cell = RelationshipTo('Cell', 'CONTAINED_BY')
    member_items = RelationshipFrom('MemberItem', 'OWNED_BY')
    member_name = StringProperty(required=True, index=True)


class MemberItem(StructuredNode):
    owning_member = RelationshipTo('CellMember', 'OWNED_BY')
    item_name = StringProperty(required=True, index=True)


def _setup_cell_data():
    cell1 = Cell().save()
    cell2 = Cell().save()
    cell1.next_cell.connect(cell2)
    cell2.next_cell.connect(cell1)

    for name in ['a1', 'a2', 'a3']:
        cell_member = CellMember(member_name=name).save()
        cell2.members.connect(cell_member)
        for item in ['_i1', '_i2', '_i3']:
            mi = MemberItem(item_name=name + item).save()
            cell_member.member_items.connect(mi)

    return cell1


def test_traverse_missing_relation():
    test_cell = _setup_cell_data()
    try:
        test_cell.traverse('next').traverse('members').traverse('member_items').run()
    except AttributeError as e:
        assert "no relationship definition" in str(e)
    else:
        assert False


def test_correct_traversal():
    test_cell = _setup_cell_data()
    results = test_cell.traverse('next_cell').traverse('members').traverse('member_items').run()
    assert len(results) == 9
    for item in results:
        assert isinstance(item, (MemberItem,))
