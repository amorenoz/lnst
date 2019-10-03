#!/bin/python3

import os
import uuid
import logging
 
from lnst.Common.Parameters import StrParam

from lnst.Controller.Recipe import BaseRecipe
from lnst.Controller.Requirements import HostReq, DeviceReq

from lnst.Controller import Controller
from lnst.Controller.RunSummaryFormatter import RunSummaryFormatter
from lnst.Controller.RecipeResults import ResultLevel
 
from lnst.Recipes.ENRT.SimpleNetworkRecipe import SimpleNetworkRecipe
from lnst.Recipes.ENRT.VhostNetPvPRecipe import VhostNetPvPRecipe


ctl = Controller(debug=1)

# official_result=no driver=ixgbe trex_dir=/mnt/testarea/trex/ guest_virtname=guest1 guest_hostname=guest1 guest_username=root guest_password=redhat guest_cpus=5,6,7,8 guest_emulatorpin=9 host1_dpdk_cores=2,3,4 host2_dpdk_    lcores=0x400 host2_dpdk_cores=0x1E nr_hugepages=13000 socket_mem=2048 pkt_size=64 test_runs=5 test_duration=60 product_name=RHEL7-OvS2.11-fast-datapath-rhel-7-candidate
guest_name="guest1"
guest_cpus="7,8,9,10" # cpu pinning: index is the vcpu
vhost_cpus="4,5,6"  # cpus used for vhost threads. need 3
guest_emulatorpin_cpu="4-6" # must contain the vhost_cpus
guest_mem_size=16777216  # FIXME: For some reason if 4GB are configured the guest crashes :/ 
trex_dir="/mnt/testarea/trex"
driver="ixgbe"


generator_dpdk_cores= "2,3,4"

#dev_intr_cpu        #IntParam(default=0)

# cpu_perf_tool = Param(default=StatCPUMeasurement)

#perf_duration = IntParam(default=60)
#perf_iterations = IntParam(default=5)
#perf_msg_size = IntParam(default=64)

#perf_usr_comment = StrParam(default="")
r = VhostNetPvPRecipe(guest_name=guest_name,
                      driver=driver,
                     guest_cpus=guest_cpus,
                     vhost_cpus=vhost_cpus,
                     guest_emulatorpin_cpu=guest_emulatorpin_cpu,
                     guest_mem_size=guest_mem_size,
                     trex_dir=trex_dir,
                     generator_dpdk_cores=generator_dpdk_cores
                     )


ctl.run(r, allow_virt=True)

summary_fmt = RunSummaryFormatter(level=ResultLevel.IMPORTANT, colourize=True)
for run in r.runs:
    logging.info(summary_fmt.format_run(run))

