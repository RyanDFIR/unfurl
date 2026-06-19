from unfurl.core import Unfurl
import unittest


class TestBase32(unittest.TestCase):

    def test_padded_b32_ascii(self):
        """ Test a simple ASCII string that is base32-encoded."""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='ORSXG5DZORSXG5DUMVZXI===')
        test.parse_queue()

        # confirm that it was decoded from b32 to a string
        self.assertEqual('string', test.nodes[2].data_type)

        # confirm that text decoded correctly
        self.assertEqual('testytesttest', test.nodes[2].value)

        # confirm the edge was labeled as base32
        self.assertEqual('b32', test.nodes[2].incoming_edge_config['label'])

    def test_unpadded_b32_ascii(self):
        """ Test a simple ASCII string that is base32-encoded, with padding removed."""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='ORSXG5DZORSXG5DUMVZXI')
        test.parse_queue()

        # confirm that it was decoded from b32 to a string
        self.assertEqual('string', test.nodes[2].data_type)

        # confirm that text decoded correctly
        self.assertEqual('testytesttest', test.nodes[2].value)

    def test_b32_decodes_to_json(self):
        """ Test a real-world base32 value that decodes to JSON (from issue #208)."""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value=('PMRGSZBCHIZDKNZZGYZTGLBCN5ZGOIR2EI2DSM3CGM3TQNBNGU4TEMZNGQYDEZBNHE3DEOBN'
                   'GJRDIYJVMQZDOMDEMUZSELBCOZSXE43JN5XCEORCGQRCYITTNFTSEORCONWFCWKBPB5HOWK2'
                   'PBVEIS2EKZGGQUKXJQ2FE5DEONUWI3SQJRHE42KMM5KWSRKXKJXWGPJCPU======'))
        test.parse_queue()

        # confirm that it was decoded from b32 to a string
        self.assertEqual('string', test.nodes[2].data_type)

        # confirm the JSON payload decoded correctly
        self.assertIn('"org":"493b3784-5923-402d-9628-2b4a5d270de3"', test.nodes[2].value)

        # confirm the decoded JSON was further parsed by the JSON parser
        decoded_values = [n.value for n in test.nodes.values()]
        self.assertIn(2579633, decoded_values)

    def test_all_letters_not_decoded(self):
        """ Values that are entirely letters are filtered out as likely words, not base32."""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='HELLOWORLD')
        test.parse_queue()

        # the only node should be the input; nothing was decoded from base32
        self.assertNotIn('b32', _edge_labels(test))

    def test_non_ascii_result_not_decoded(self):
        """ Base32 that doesn't decode to ASCII should not produce a node."""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='DEADBEEF23')
        test.parse_queue()

        self.assertNotIn('b32', _edge_labels(test))

    def test_overlap_twin_self_resolves_via_printability(self):
        """ b32 and b64 are independent parsers. For a value that's valid under
        both alphabets, the printable gate keeps only the useful decode: 'unfurltest'
        base32-encodes to a length-16 value (also a valid base64 length), but the
        base64 interpretation is non-printable garbage and is dropped."""

        import base64 as _b64
        value = _b64.b32encode(b'unfurltest').decode()

        test = Unfurl()
        test.add_to_queue(data_type='url', key=None, value=value)
        test.parse_queue()

        labels = _edge_labels(test)
        self.assertIn('b32', labels)
        self.assertNotIn('b64', labels)
        self.assertIn('unfurltest', [n.value for n in test.nodes.values()])


    def test_explicit_base32_decodes_short_value(self):
        """ A node explicitly labelled 'base32' decodes even when below the
        auto-detect minimum length (heuristics are bypassed)."""

        test = Unfurl()
        # 'foo' base32-encodes to 'MZXW6' (5 chars, under the auto-detect floor).
        test.add_to_queue(data_type='base32', key=None, value='MZXW6')
        test.parse_queue()

        self.assertEqual('b32', test.nodes[2].incoming_edge_config['label'])
        self.assertEqual('foo', test.nodes[2].value)


def _edge_labels(test):
    """ Collect the incoming-edge labels for all nodes in the graph."""
    labels = []
    for node in test.nodes.values():
        config = getattr(node, 'incoming_edge_config', None)
        if config:
            labels.append(config.get('label'))
    return labels


if __name__ == '__main__':
    unittest.main()
