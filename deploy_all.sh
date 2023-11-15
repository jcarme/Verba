#!/bin/bash

NB_TENANTS=3

#repeat NB_TENANTS times the call to script deploy.sh, with i as the tenant number as argument
for ((i=0;i<$NB_TENANTS;i++)); do
    nohup ./deploy.sh $i
done
