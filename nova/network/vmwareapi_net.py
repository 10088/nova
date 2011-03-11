# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2011 Citrix Systems, Inc.
# Copyright 2011 OpenStack LLC.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Implements vlans for vmwareapi
"""

from nova import db
from nova import exception
from nova import flags
from nova import log as logging
from nova import utils
from nova.virt.vmwareapi_conn import VMWareAPISession
from nova.virt.vmwareapi.network_utils import NetworkHelper

LOG = logging.getLogger("nova.network.vmwareapi_net")

FLAGS = flags.FLAGS
flags.DEFINE_string('vlan_interface', 'vmnic0',
                    'Physical network adapter name in VMware ESX host for '
                    'vlan networking')


def ensure_vlan_bridge(vlan_num, bridge, net_attrs=None):
    """Create a vlan and bridge unless they already exist"""
    #open vmwareapi session
    host_ip = FLAGS.vmwareapi_host_ip
    host_username = FLAGS.vmwareapi_host_username
    host_password = FLAGS.vmwareapi_host_password
    if not host_ip or host_username is None or host_password is None:
        raise Exception(_("Must specify vmwareapi_host_ip,"
                        "vmwareapi_host_username "
                        "and vmwareapi_host_password to use"
                        "connection_type=vmwareapi"))
    session = VMWareAPISession(host_ip, host_username, host_password,
                               FLAGS.vmwareapi_api_retry_count)
    vlan_interface = FLAGS.vlan_interface
    #Check if the vlan_interface physical network adapter exists on the host
    if not NetworkHelper.check_if_vlan_interface_exists(session,
                                                        vlan_interface):
        raise exception.NotFound(_("There is no physical network adapter with "
                          "the name %s on the ESX host") % vlan_interface)

    #Get the vSwitch associated with the Physical Adapter
    vswitch_associated = NetworkHelper.get_vswitch_for_vlan_interface(
                                        session, vlan_interface)
    if vswitch_associated is None:
        raise exception.NotFound(_("There is no virtual switch associated "
            "with the physical network adapter with name %s") %
            vlan_interface)
    #check whether bridge already exists and retrieve the the ref of the
    #network whose name_label is "bridge"
    network_ref = NetworkHelper.get_network_with_the_name(session, bridge)
    if network_ref == None:
        #Create a port group on the vSwitch associated with the vlan_interface
        #corresponding physical network adapter on the ESX host
        NetworkHelper.create_port_group(session, bridge, vswitch_associated,
                                vlan_num)
    else:
        #Get the vlan id and vswitch corresponding to the port group
        pg_vlanid, pg_vswitch = \
            NetworkHelper.get_vlanid_and_vswicth_for_portgroup(session, bridge)

        #Check if the vsiwtch associated is proper
        if pg_vswitch != vswitch_associated:
            raise exception.Invalid(_("vSwitch which contains the port group "
                            "%(bridge)s is not associated with the desired "
                            "physical adapter. Expected vSwitch is "
                            "%(vswitch_associated)s, but the one associated"
                            " is %(pg_vswitch)s") %\
                            {"bridge": bridge,
                             "vswitch_associated": vswitch_associated,
                             "pg_vswitch": pg_vswitch})

        #Check if the vlan id is proper for the port group
        if pg_vlanid != vlan_num:
            raise exception.Invalid(_("VLAN tag is not appropriate for the "
                            "port group %(bridge)s. Expected VLAN tag is "
                            "%(vlan_num)s, but the one associated with the "
                            "port group is %(pg_vlanid)s") %\
                            {"bridge": bridge,
                             "vlan_num": vlan_num,
                             "pg_vlanid": pg_vlanid})
