#!/usr/bin/env python3

from glob import glob
import os.path
import sys
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape, quoteattr

from carriersettings_pb2 import CarrierList, CarrierSettings, \
    MultiCarrierSettings

pb_path = sys.argv[1]

carrier_list = CarrierList()
all_settings = {}
for filename in glob(os.path.join(pb_path, '*.pb')):
    with open(filename, 'rb') as pb:
        if os.path.basename(filename) == 'carrier_list.pb':
            carrier_list.ParseFromString(pb.read())
        elif os.path.basename(filename) == 'others.pb':
            settings = MultiCarrierSettings()
            settings.ParseFromString(pb.read())
            for setting in settings.setting:
                assert setting.canonicalName not in all_settings
                all_settings[setting.canonicalName] = setting
        else:
            setting = CarrierSettings()
            setting.ParseFromString(pb.read())
            assert setting.canonicalName not in all_settings
            all_settings[setting.canonicalName] = setting

# Unfortunately, python processors like xml and lxml, as well as command-line
# utilities like tidy, do not support the exact style used by AOSP for
# apns-full-conf.xml:
#
#  * indent: 2 spaces
#  * attribute indent: 4 spaces
#  * blank lines between elements
#  * attributes after first indented on separate lines
#  * closing tags of multi-line elements on separate, unindented lines
#
# Therefore, we build the file without using an XML processor.


class ApnElement:
    def __init__(self, apn, carrier_id):
        self.apn = apn
        self.carrier_id = carrier_id
        self.attributes = {}
        self.add_attributes()

    def add_attribute(self, key, field=None, value=None):
        if value is not None:
            self.attributes[key] = value
        else:
            if field is None:
                field = key
            if self.apn.HasField(field):
                enum_type = self.apn.DESCRIPTOR.fields_by_name[field].enum_type
                value = getattr(self.apn, field)
                if enum_type is None:
                    if isinstance(value, bool):
                        self.attributes[key] = str(value).lower()
                    else:
                        self.attributes[key] = str(value)
                else:
                    self.attributes[key] = \
                        enum_type.values_by_number[value].name

    def add_attributes(self):
        self.add_attribute('mcc', value=self.carrier_id.mccMnc[:3])
        self.add_attribute('mnc', value=self.carrier_id.mccMnc[3:])
        self.add_attribute('apn', 'value')
        self.add_attribute('proxy')
        self.add_attribute('port')
        self.add_attribute('mmsc')
        self.add_attribute('mmsproxy', 'mmscProxy')
        self.add_attribute('mmsport', 'mmscProxyPort')
        self.add_attribute('user')
        self.add_attribute('password')
        self.add_attribute('server')
        self.add_attribute('authtype')
        self.add_attribute(
            'type',
            value=','.join(
                apn.DESCRIPTOR.fields_by_name[
                    'type'
                ].enum_type.values_by_number[i].name
                for i in self.apn.type
            ).lower(),
        )
        self.add_attribute('protocol')
        self.add_attribute('roaming_protocol', 'roamingProtocol')
        self.add_attribute('carrier_enabled', 'carrierEnabled')
        self.add_attribute('bearer_bitmask', 'bearerBitmask')
        self.add_attribute('profile_id', 'profileId')
        self.add_attribute('modem_cognitive', 'modemCognitive')
        self.add_attribute('max_conns', 'maxConns')
        self.add_attribute('wait_time', 'waitTime')
        self.add_attribute('max_conns_time', 'maxConnsTime')
        self.add_attribute('mtu')
        mvno = self.carrier_id.WhichOneof('mvno')
        if mvno:
            self.add_attribute(
                'mvno_type',
                value='gid' if mvno.startswith('gid') else mvno,
            )
            self.add_attribute(
                'mvno_match_data',
                value=getattr(self.carrier_id, mvno),
            )
        self.add_attribute('apn_set_id', 'apnSetId')
        # No source for integer carrier_id?
        self.add_attribute('skip_464xlat', 'skip464Xlat')
        self.add_attribute('user_visible', 'userVisible')
        self.add_attribute('user_editable', 'userEditable')


with open('apns-full-conf.xml', 'w') as f:
    f.write('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n\n')
    f.write('<apns version="8">\n\n')

    for entry in carrier_list.entry:
        setting = all_settings[entry.canonicalName]
        for apn in setting.apns.apn:
            f.write('  <apn carrier={}\n'.format(quoteattr(apn.name)))
            apn_element = ApnElement(apn, entry.carrierId)
            for (key, value) in apn_element.attributes.items():
                f.write('      {}={}\n'.format(escape(key), quoteattr(value)))
            f.write('  />\n\n')

    f.write('</apns>\n')

# Test XML parsing.
ET.parse('apns-full-conf.xml')
