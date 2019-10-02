import xml.etree.ElementTree as ET

from lnst.Controller import HostReq, DeviceReq
from lnst.Common.Logs import log_exc_traceback
from lnst.Common.Parameters import Param, IntParam, StrParam
from lnst.Common.IpAddress import ipaddress
from lnst.RecipeCommon.Ping import PingTestAndEvaluate
from lnst.Tests import Ping
from lnst.Devices import BridgeDevice

from lnst.RecipeCommon.Perf.Recipe import Recipe as PerfRecipe
from lnst.RecipeCommon.Perf.Measurements import StatCPUMeasurement
from lnst.RecipeCommon.LibvirtControl import LibvirtControl

class VhostPvPTestConf(object):
    class HostConf(object):
        def __init__(self):
            self.host = None
            self.nics = []

    class DUTConf(HostConf):
        def __init__(self):
            super(VhostPvPTestConf.DUTConf, self).__init__()
            self.vm_ports = None

    class GuestConf(HostConf):
        def __init__(self):
            super(VhostPvPTestConf.GuestConf, self).__init__()
            self.name = ""
            self.virtctl = None
            self.vhost_nics = None

    def __init__(self):
        self.generator = self.HostConf()
        self.dut = self.DUTConf()
        self.guest = self.GuestConf()


class VhostNetPvPRecipe(PingTestAndEvaluate, PerfRecipe):
    generator_req = HostReq()
    generator_req.eth0 = DeviceReq(label="net1")
    generator_req.eth1 = DeviceReq(label="net2")

    host_req = HostReq(with_guest="yes")
    host_req.eth0 = DeviceReq(label="net1")
    host_req.eth1 = DeviceReq(label="net2")

    #driver = StrParam(mandatory=True) I don't thik I need a driver requirement
    trex_dir = StrParam(mandatory=True) # FIXME: Add a default value

    guest_name = StrParam(mandatory=True)
    guest_cpus = StrParam(mandatory=True)
    guest_emulatorpin_cpu = StrParam(mandatory=True)
    guest_mem_size = IntParam(default=16777216)

    # TODO: Study the possibility of adding more forwarding engines 
    # like xdp or tc
    guest_fwd = StrParam(default='bridge')
    host_fwd = StrParam(default='bridge')

    guest_macs = Param(default=['02:fa:fe:fa:fe:01', '02:fa:fe:fa:fe:02'])


    generator_dpdk_cores = StrParam(mandatory=True)
    nr_hugepages = IntParam(default=13000)

    cpu_perf_tool = Param(default=StatCPUMeasurement)

    perf_duration = IntParam(default=60)
    perf_iterations = IntParam(default=5)
    perf_msg_size = IntParam(default=64)

    perf_streams = IntParam(default=1)

    def test(self):
        self.check_dependencies()
        self.warmup()
        self.pvp_test()


    def check_dependencies(self):
        pass

    def warmup(self):
        try:
            self.warmup_configuration()
            self.warmup_pings()
        finally:
            self.warmup_deconfiguration()


    def warmup_configuration(self):
        m1, m2 = self.matched.generator_req, self.matched.host_req
        m1.eth0.up()
        m1.eth1.up()
        m1.eth0.ip_add(ipaddress("192.168.1.1/24"))
        m1.eth1.ip_add(ipaddress("192.168.1.3/24"))

        m2.eth0.up()
        m2.eth1.up()
        m2.eth0.ip_add(ipaddress("192.168.1.2/24"))
        m2.eth1.ip_add(ipaddress("192.168.1.4/24"))

    def warmup_pings(self):
        m1, m2 = self.matched.generator_req, self.matched.host_req

        jobs = []
        jobs.append(m1.run(Ping(interface=m1.eth0.ips[0], dst=m2.eth0.ips[0]), bg=True))
        jobs.append(m1.run(Ping(interface=m1.eth1.ips[0], dst=m2.eth1.ips[0]), bg=True))
        jobs.append(m2.run(Ping(interface=m2.eth0.ips[0], dst=m1.eth0.ips[0]), bg=True))
        jobs.append(m2.run(Ping(interface=m2.eth1.ips[0], dst=m1.eth1.ips[0]), bg=True))

        for job in jobs:
            job.wait()
        #TODO eval

    def warmup_deconfiguration(self):
        m1, m2 = self.matched.generator_req, self.matched.host_req
        m1.eth0.ip_flush()
        m1.eth1.ip_flush()

        m2.eth0.ip_flush()
        m2.eth1.ip_flush()

    def pvp_test(self):
        try:
            config = VhostPvPTestConf()
            self.test_wide_configuration(config)

        #    perf_config = self.generate_perf_config(config)
        #    result = self.perf_test(perf_config)
        #    self.perf_report_and_evaluate(result)
        finally:
            self.test_wide_deconfiguration(config)

    def test_wide_configuration(self, config):

        #Not sure if needed
        #host.run("service irqbalance stop")

        config.generator.host = self.matched.generator_req
        config.generator.nics.append(self.matched.generator_req.eth0)
        config.generator.nics.append(self.matched.generator_req.eth1)

        self.matched.generator_req.eth0.ip_add(ipaddress("192.168.1.1/24"))
        self.matched.generator_req.eth1.ip_add(ipaddress("192.168.1.3/24"))
        self.matched.generator_req.eth0.up()
        self.matched.generator_req.eth1.up()

        self.base_dpdk_configuration(config.generator)

        config.dut.host = self.matched.host_req
        config.dut.nics.append(self.matched.host_req.eth0)
        config.dut.nics.append(self.matched.host_req.eth1)
        self.matched.host_req.eth0.ip_add(ipaddress("192.168.1.2/24"))
        self.matched.host_req.eth1.ip_add(ipaddress("192.168.1.4/24"))
        self.matched.host_req.eth0.up()
        self.matched.host_req.eth1.up()

        self.host_forwarding_configuration(config.dut)

        self.init_guest_virtctl(config.dut, config.guest)
        self.shutdown_guest(config.guest)
        self.configure_guest_xml(config.dut, config.guest)

        self.host_forwarding_vm_configuration(config.dut, config.guest)

        guest = self.create_guest(config.dut, config.guest)
        self.guest_forwarding(config.guest)

        return config

    def test_wide_deconfiguration(self, config):
        try:
            self.guest_deconfigure(config.guest)
        except:
            log_exc_traceback()

        try:
            self.host_forwarding_vm_deconfiguration(config.dut, config.guest)
        except:
            log_exc_traceback()

        try:
            self.host_forwarding_deconfiguration(config.dut)
        except:
            log_exc_traceback()

        try:
            self.base_dpdk_deconfiguration(config.generator)
        except:
            log_exc_traceback()

        try:
            #returning the guest to the original running state
            self.shutdown_guest(config.guest)
            if config.guest.virtctl:
                config.guest.virtctl.vm_start(config.guest.name)
        except:
            log_exc_traceback()

        try:
            config.generator.host.run("service irqbalance start")
        except:
            log_exc_traceback()


    def host_forwarding_vm_configuration(self, host_conf, guest_conf):
        """
        VM - specific forwarding configuration
        """
        # Nothing to do fow now, maybe later configure xdp flows
        pass

    def host_forwarding_vm_deconfiguration(self, host_conf, guest_conf):
        """
        VM - specific forwarding deconfiguration
        """
        # Nothing to do fow now, maybe later configure xdp flows
        pass

    def host_forwarding_configuration(self, host_conf):
        if (self.params.host_fwd == 'bridge'):
            host_conf.bridges=[]
            host_conf.host.br0 = BridgeDevice()
            host_conf.host.br1 = BridgeDevice()

            host_conf.host.br0.slave_add(
                    host_conf.nics[0])
            host_conf.host.br1.slave_add(
                    host_conf.nics[1])

            host_conf.bridges.append(host_conf.host.br0)
            host_conf.bridges.append(host_conf.host.br1)

        else:
            # TBD
            return

    def host_forwarding_deconfiguration(self, host_conf):
        if (self.params.host_fwd == 'bridge'):
            if host_conf.host.br0:
                host_conf.host.br0.slave_del(
                    host_conf.nics[0])
            if host_conf.host.br1:
                host_conf.host.br1.slave_del(
                    host_conf.nics[1])
        else:
            # TBD
            return

    def init_guest_virtctl(self, host_conf, guest_conf):
        host = host_conf.host

        guest_conf.name = self.params.guest_name
        guest_conf.virtctl = host.init_class(LibvirtControl)

    def shutdown_guest(self, guest_conf):
        virtctl = guest_conf.virtctl
        if virtctl:
            virtctl.vm_shutdown(guest_conf.name)
            self.ctl.wait_for_condition(lambda:
                not virtctl.is_vm_running(guest_conf.name))

    def configure_guest_xml(self, host_conf, guest_conf):
        virtctl = guest_conf.virtctl
        guest_xml = ET.fromstring(virtctl.vm_XMLDesc(guest_conf.name))
        guest_conf.libvirt_xml = guest_xml

        guest_conf.vhost_nics = []
        vhosts = guest_conf.vhost_nics
        for i, nic in enumerate(host_conf.nics):
            self._xml_add_vhostnet_dev(
               guest_xml,
               "vhostnet-{i}".format(i=i),
               host_conf.bridges[i],
               self.params.guest_macs[i])
            vhosts.append(self.params.guest_macs[i])

            #vhosts.append((path, nic.hwaddr)) # Do't know what to append here yet

        # Not sure if we need numa configuration in the guest yet:
        #cpu = guest_xml.find("cpu")
        #numa = ET.SubElement(cpu, 'numa')
        #ET.SubElement(numa, 'cell', id='0', cpus='0',
        #              memory=str(self.params.guest_mem_size), unit='KiB',
        #              memAccess='shared')

        #cputune = ET.SubElement(guest_xml, "cputune")
        #for i, cpu_id in enumerate(self.params.guest_cpus.split(',')):
        #    ET.SubElement(cputune, "vcpupin", vcpu=str(i), cpuset=str(cpu_id))

        #ET.SubElement(cputune,
        #              "emulatorpin",
        #              cpuset=str(self.params.guest_emulatorpin_cpu))

        #memoryBacking = ET.SubElement(guest_xml, "memoryBacking")
        #hugepages = ET.SubElement(memoryBacking, "hugepages")
        #ET.SubElement(hugepages, "page", size="2", unit="M", nodeset="0")

        return guest_xml


    def base_dpdk_configuration(self, dpdk_host_cfg):
        host = dpdk_host_cfg.host

        for nic in dpdk_host_cfg.nics:
            nic.enable_readonly_cache()

        #TODO service should be a host method
        host.run("service irqbalance stop")

        # this will pin all irqs to cpu #0
        self._pin_irqs(host, 0)
        host.run("echo -n {} /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages"
               .format(self.params.nr_hugepages))

        host.run("modprobe vfio-pci")
        for nic in dpdk_host_cfg.nics:
            host.run("driverctl set-override {} vfio-pci".format(nic.bus_info))

    def base_dpdk_deconfiguration(self, dpdk_host_cfg):
        host = dpdk_host_cfg.host
        #TODO service should be a host method
        host.run("service irqbalance start")
        for nic in dpdk_host_cfg.nics:
            job = host.run("driverctl unset-override {}".format(nic.bus_info),
                           bg=True)

            if not job.wait(10):
                job.kill()

    def create_guest(self, host_conf, guest_conf):
        host = host_conf.host
        virtctl = guest_conf.virtctl
        guest_xml = guest_conf.libvirt_xml

        str_xml = ET.tostring(guest_xml, encoding='utf8', method='xml')
        virtctl.createXML(str_xml.decode('utf8'))


        guest_ip_job = host.run("gethostip -d {}".format(guest_conf.name))
        guest_ip = guest_ip_job.stdout.strip()
        print('guest-ip is {}'.format(guest_ip))

        guest = self.ctl.connect_host(guest_ip, timeout=60, machine_id="guest1")
        guest_conf.host = guest

        for i, nic in enumerate(guest_conf.vhost_nics):
            #FIXME: generalize the content of vhost_nics
            guest.map_device("eth{}".format(i), dict(hwaddr=nic))
            device = getattr(guest, "eth{}".format(i))
            guest_conf.nics.append(device)
        return guest

    def guest_forwarding(self, guest_conf):
        guest = guest_conf.host
        if (self.params.guest_fwd == 'bridge'):
            guest.bridge = BridgeDevice()
            guest.bridge.name = 'guestbr0'
            for nic in guest_conf.nics:
                guest.bridge.slave_add(nic)
                nic.up()

        guest.run("echo 1 > /proc/sys/net/ipv4/ip_forward")

    def guest_deconfigure(self, guest_conf):
        if guest_conf.host:
            guest_conf.host.run("echo 0 > /proc/sys/net/ipv4/ip_forward")

    def _xml_add_vhostnet_dev(self, guest_xml, name, bridge, mac_addr):
        devices = guest_xml.find("devices")

        interface = ET.SubElement(devices, 'interface', type='bridge')
        ET.SubElement(interface, 'source', bridge=str(bridge.name))
        ET.SubElement(interface, 'mac', address=str(mac_addr))
        ET.SubElement(interface, 'model', type='virtio')
        ET.SubElement(interface, 'driver', name='vhost')
        # TODO: Add driver suboptions
        return guest_xml

    def _pin_irqs(self, host, cpu):
        mask = 1 << cpu
        host.run("MASK={:x}; "
                 "for i in `ls -d /proc/irq/[0-9]*` ; "
                    "do echo $MASK > ${{i}}/smp_affinity ; "
                 "done".format(cpu))
