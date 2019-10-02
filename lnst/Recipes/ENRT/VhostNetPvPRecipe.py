from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Common.Parameters import Param, IntParam, StrParam, BoolParam
from lnst.Common.IpAddress import ipaddress
from lnst.RecipeCommon.Ping import PingTestAndEvaluate, PingConf

class VhostPvPTestConf(object):
    class HostConf(object):
        def __init__(self):
            self.host = None
            self.nics = []

    class DUTConf(HostConf):
        def __init__(self):
            super(PvPTestConf.DUTConf, self).__init__()
            self.vm_ports = None

    class GuestConf(HostConf):
        def __init__(self):
            super(PvPTestConf.GuestConf, self).__init__()
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
    generator_req.eth1 = DeviceReq(label="net1")

    host_req = HostReq(with_guest="yes")
    host_req.eth0 = DeviceReq(label="net1")
    host_req.eth1 = DeviceReq(label="net1")

    #driver = StrParam(mandatory=True) I don't thik I need a driver requirement
    trex_dir = StrParam(mandatory=True) # FIXME: Add a default value

    guest_name = StrParam(mandatory=True)
    guest_cpus = StrParam(mandatory=True)
    guest_emulatorpin_cpu = StrParam(mandatory=True)
    guest_mem_size = IntParam(default=16777216)
    guest_fwd = 'bridge' # TODO: Study the possibility of adding more forwarding engines like xdp or tc


    generator_dpdk_cores = StrParam(mandatory=True)

    cpu_perf_tool = Param(default=StatCPUMeasurement)

    perf_duration = IntParam(default=60)
    perf_iterations = IntParam(default=5)
    perf_msg_size = IntParam(default=64)

    perf_streams = IntParam(default=1)

    def test(self):
        self.check_dependencies()
        self.warmup()


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
        m1.eth0.ip_add(ipaddress("192.168.1.1/24"))
        m1.eth1.ip_add(ipaddress("192.168.1.3/24"))

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


