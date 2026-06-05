library(ggplot2)
#File directory
setwd("F:/Ostracod Respirometry/Prelim data")

prelim_rmr<-read.csv("prelim_rmr.csv")

prelim_rmr$wrap <- factor(prelim_rmr$wrap)
prelim_rmr$time <- factor(prelim_rmr$time)

interactive <- lm(rmr ~ time * wrap, data = prelim_rmr)
summary(interactive)

ggplot(prelim_rmr, aes(x = time, y = rmr, fill = wrap)) +
  geom_boxplot(color = "black") + scale_fill_manual(values = c("white", "grey"),labels = c("unwrapped" = "Unwrapped", "wrapped" = "Wrapped"))+ theme_classic() + labs(x = "Time of Day", fill = "Wrapping",y = bquote("Routine metabolic rate (" * mu * "L " * O[2] * "/mg/h)"))+scale_x_discrete(labels = c("day" = "Day", "night" = "Night"))

