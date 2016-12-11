import log

from cms import config


cmslog = log.Log(config.log)
httplog = log.HTTPLog(config.log, config.httplog)
