from unfurl.core import Unfurl
import unittest


class TestSafeLinks(unittest.TestCase):

    def _node_labels(self, test):
        return [n.label for n in test.nodes.values() if n.label]

    def test_safelinks_decodes_destination(self):
        """SafeLinks wrapper should annotate the inner URL (parse_url unfurls
        it separately) and decompose the `data` field into labeled descriptors.
        """
        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://nam04.safelinks.protection.outlook.com/?'
                  'url=https%3A%2F%2Fexample.com%2Fphish%3Fid%3D42&'
                  'data=05%7C02%7Calice%40contoso.com%7Cabc-sender-guid%7Cdef-tenant-guid%7C0%7C0%7C638400000000000000%7CUnknown%7CTWFpbGZsb3d8eyJWIjoiMC4wLjAwMDAifQ%3D%3D&'
                  'sdata=AAAAAAAAAAA%3D&'
                  'reserved=0')
        test.parse_queue()

        labels = self._node_labels(test)

        # SafeLinks parser annotates the `url` query pair; the destination
        # itself is unfurled separately by parse_url (no double-parse).
        self.assertTrue(
            any('Wrapped destination URL' in l for l in labels),
            f'wrapped destination descriptor missing; labels={labels}')
        sl_url_descriptors = [n for n in test.nodes.values()
                              if n.data_type == 'descriptor'
                              and 'Wrapped destination URL' in (n.value or '')]
        self.assertEqual(len(sl_url_descriptors), 1,
                         'expected exactly one SafeLinks destination descriptor')

        # `data` field components surface as labeled descriptors
        for expected in (
                'Recipient (Field 2): alice@contoso.com',
                'Message GUID (Field 3): abc-sender-guid',
                'Tenant GUID (Field 4): def-tenant-guid',
                'Timestamp (Field 7): 638400000000000000',
                'Scan verdict (Field 8): Unknown',
        ):
            self.assertTrue(any(expected in l for l in labels),
                            f'expected {expected!r}; labels={labels}')

        # Position 9 (the base64 scan payload) is emitted as a raw string
        # so the chain runs: parse_base64 decodes -> parse_url splits on '|'
        # -> parse_json descends into the JSON. The component name ('Mailflow')
        # ends up as a child of the decoded payload, not a sibling of pos 9.
        payload_node = next((n for n in test.nodes.values()
                             if (n.label or '').startswith('Scan payload (Field 9):')),
                            None)
        self.assertIsNotNone(payload_node, 'base64 scan payload node missing')
        # The decoded string should be a child of the payload node
        decoded_children = [n for n in test.nodes.values()
                            if n.parent_id == payload_node.node_id]
        self.assertTrue(any('Mailflow' in str(n.value) for n in decoded_children),
                        f'decoded payload not a child of base64 node; '
                        f'children={[(n.data_type,str(n.value)[:40]) for n in decoded_children]}')
        # And the component name should appear as a grandchild (parse_url
        # split the 'Mailflow|{...}' decoded string).
        decoded_node = decoded_children[0]
        grandchildren = [n for n in test.nodes.values()
                         if n.parent_id == decoded_node.node_id]
        self.assertTrue(any(str(n.value) == 'Mailflow' for n in grandchildren),
                        f'component name not a grandchild of base64 node; '
                        f'grandchildren={[(n.data_type,str(n.value)[:40]) for n in grandchildren]}')

        # Position 7 should pass through parse_timestamp as 'datetime-ticks'
        # and yield a human-readable date.
        ticks_node = next((n for n in test.nodes.values()
                           if n.data_type == 'datetime-ticks'), None)
        self.assertIsNotNone(ticks_node, 'no datetime-ticks node emitted')
        self.assertEqual('638400000000000000', ticks_node.value)
        # parse_timestamp converts and adds a 'timestamp.datetime-ticks' child
        converted = [n.value for n in test.nodes.values()
                     if n.data_type == 'timestamp.datetime-ticks']
        self.assertTrue(any('2024-01-04' in str(v) for v in converted),
                        f'parse_timestamp did not decode ticks; converted={converted}')


        # sdata labeled as a signature
        self.assertTrue(any('Signature Data' in l for l in labels),
                        f'sdata not labeled as a signature; labels={labels}')

    def test_safelinks_double_encoded_data(self):
        """Some captured Safe Links have a double-URL-encoded `data` field where
        pipes survive as %7C. The parser should still decompose it."""
        test = Unfurl()
        # The `data` value here is single-URL-encoded by the time it arrives at
        # the parser (parse_qsl unquoted the outer layer once); pipes are still
        # %7C.
        test.add_to_queue(
            data_type='url', key=None,
            value='https://apac01.safelinks.protection.outlook.com/?'
                  'url=https%253A%252F%252Fexample.com%252F&'
                  'data=04%257C01%257C%257Cabc-sender%257Cdef-tenant%257C0%257C0%257C637720111682524488&'
                  'reserved=0')
        test.parse_queue()

        labels = self._node_labels(test)
        # If the %7C fallback worked, we should see fields beyond just Version
        self.assertTrue(any('Message GUID (Field 3): abc-sender' in l for l in labels),
                        f'double-encoded data not split; labels={labels}')
        self.assertTrue(any('Tenant GUID (Field 4): def-tenant' in l for l in labels),
                        f'double-encoded data not split; labels={labels}')

    def test_safelinks_only_fires_on_safelinks_domain(self):
        """Look-alike domains must not trigger the parser."""
        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://example.com/?url=https%3A%2F%2Fevil.example%2F&data=a%7Cb%7Cc')
        test.parse_queue()

        labels = self._node_labels(test)
        self.assertFalse(any('Signature Data' in l for l in labels),
                         'SafeLinks parser fired on non-SafeLinks domain')
        self.assertFalse(any('Recipient:' in l for l in labels),
                         'SafeLinks parser fired on non-SafeLinks domain')


if __name__ == '__main__':
    unittest.main()
