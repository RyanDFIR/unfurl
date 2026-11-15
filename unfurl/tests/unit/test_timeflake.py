from unfurl.core import Unfurl
import unittest


def get_nodes_by_type(unfurl_instance, data_type):
    return [n for n in unfurl_instance.nodes.values() if n.data_type == data_type]


def unfurl_value(value):
    test = Unfurl(remote_lookups=False)
    test.add_to_queue(data_type='url', key=None, value=value)
    test.parse_queue()
    return test


class TestTimeflake(unittest.TestCase):
    # The same Timeflake in each of its forms, from the Timeflake README
    HEX = '016fb4209023b444fd07590f81b7b0eb'
    BASE62 = '02i2XhN7hAuaFh3MwztcMd'
    DASHED = '016fb420-9023-b444-fd07-590f81b7b0eb'

    def assert_decoded(self, test, value):
        timeflake_nodes = get_nodes_by_type(test, 'timeflake')
        self.assertEqual(1, len(timeflake_nodes))
        self.assertEqual(value, timeflake_nodes[0].value)

        epoch_nodes = get_nodes_by_type(test, 'epoch-milliseconds')
        self.assertEqual(1, len(epoch_nodes))
        self.assertEqual(1579275030563, epoch_nodes[0].value)

        timestamp_nodes = get_nodes_by_type(test, 'timestamp.epoch-milliseconds')
        self.assertEqual(1, len(timestamp_nodes))
        self.assertEqual('2020-01-17 15:30:30.563+00:00', timestamp_nodes[0].value)

        random_nodes = [n for n in get_nodes_by_type(test, 'descriptor') if str(n.label).startswith('Random: ')]
        self.assertEqual(1, len(random_nodes))
        self.assertEqual('b444fd07590f81b7b0eb', random_nodes[0].value)

        self.assertTrue(test.queue.empty())

    def test_timeflake_hex(self):
        """ The hex form is decoded, and the hash parser adds nothing under the Timeflake node """

        test = unfurl_value(self.HEX)
        self.assert_decoded(test, self.HEX)

        timeflake_node = get_nodes_by_type(test, 'timeflake')[0]
        child_types = sorted(
            n.data_type for n in test.nodes.values()
            if any(p.node_id == timeflake_node.node_id for p in test.get_predecessor_node(n) or []))
        self.assertEqual(['descriptor', 'epoch-milliseconds'], child_types)

        # It is the same shape as an MD5, so that reading is still offered, off the source value
        self.assertEqual(1, len(get_nodes_by_type(test, 'hash.md5')))

    def test_timeflake_base62(self):
        """ The base62 form decodes to the same timestamp and random bits """

        self.assert_decoded(unfurl_value(self.BASE62), self.BASE62)

    def test_timeflake_dashed(self):
        """ The UUID form, with a version position no RFC UUID uses, is decoded """

        test = unfurl_value(self.DASHED)
        self.assert_decoded(test, self.DASHED)
        self.assertEqual([], get_nodes_by_type(test, 'uuid'))

    def test_timeflake_in_url(self):
        """ A Timeflake as a path segment or a query value is found once """

        test = unfurl_value(f'https://example.com/items/{self.BASE62}?ref={self.HEX}')
        values = sorted(n.value for n in get_nodes_by_type(test, 'timeflake'))
        self.assertEqual(sorted([self.BASE62, self.HEX]), values)

    def test_whole_path_not_duplicated(self):
        """ A one-segment path that is only a Timeflake yields one node, from the segment """

        test = unfurl_value(f'https://example.com/{self.HEX}')
        timeflake_nodes = get_nodes_by_type(test, 'timeflake')
        self.assertEqual(1, len(timeflake_nodes))
        self.assertEqual('url.path.segment', test.get_predecessor_node(timeflake_nodes[0])[0].data_type)

    def test_uuid_shaped_but_not_rfc(self):
        """ UUID-shaped, version position 4, but a variant no RFC UUID has: read as time + random """

        test = unfurl_value('https://example.com/articles/01955e38-469a-49f3-1cd7-524cc4f2a751/index.html')

        self.assertEqual(1, len(get_nodes_by_type(test, 'uuid')))
        self.assertEqual([], get_nodes_by_type(test, 'timeflake'))

        parsed_nodes = get_nodes_by_type(test, 'uuid-parsed')
        self.assertEqual(1, len(parsed_nodes))
        self.assertIn('Timeflake', parsed_nodes[0].label)

        epoch_nodes = get_nodes_by_type(test, 'epoch-milliseconds')
        self.assertEqual(1, len(epoch_nodes))
        self.assertEqual(0x01955e38469a, epoch_nodes[0].value)

    def test_uuidv7_left_to_uuid_parser(self):
        """ A real UUIDv7 starts with the same kind of timestamp; it stays a UUIDv7 """

        test = unfurl_value('https://example.com/trends/01963b17-e4c4-7c22-885d-b962b8f34834')

        self.assertEqual([], get_nodes_by_type(test, 'timeflake'))
        parsed_nodes = get_nodes_by_type(test, 'uuid-parsed')
        self.assertEqual(1, len(parsed_nodes))
        self.assertIn('Version 7', parsed_nodes[0].label)

    def test_uuidv4_left_to_uuid_parser(self):
        """ A valid UUIDv4 that happens to start like a recent time is still a UUIDv4 """

        test = unfurl_value('0190f8b9-cbfe-4c3a-9677-4eda0dadd49c')

        self.assertEqual([], get_nodes_by_type(test, 'timeflake'))
        parsed_nodes = get_nodes_by_type(test, 'uuid-parsed')
        self.assertEqual(1, len(parsed_nodes))
        self.assertIn('Version 4', parsed_nodes[0].label)

    def test_implausible_timestamp_ignored(self):
        """ Same shapes, but the first 48 bits are not a time since 2020 """

        for value in ('5d41402abc4b2a76b9719d911017c592',      # MD5 of "hello"
                      '0010a1b2-c3d4-e5f6-a7b8-c9d0e1f2a3b4',  # 1970
                      '4uLU6hMCjMI75M1A2tKUQC',                # Spotify-style ID
                      '02i2XhN7hAuaFh3Mwztc'):                 # too short
            with self.subTest(value=value):
                self.assertEqual([], get_nodes_by_type(unfurl_value(value), 'timeflake'))

    def test_base62_lookalikes_ignored(self):
        """ 22 characters in the time window, but digits only or one case only: not a Timeflake """

        for value in ('0317304151742851397857', '030431otz3lav2s8s1vt3d', '0302PEESIPAD1CN0IN0SCE'):
            with self.subTest(value=value):
                self.assertEqual([], get_nodes_by_type(unfurl_value(value), 'timeflake'))


if __name__ == '__main__':
    unittest.main()
