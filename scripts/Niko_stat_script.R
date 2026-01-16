library(tidyverse)
library(readxl)
library(ggpubr)

dat <- read.csv("./mass_rmr.txt")

dat %>% filter(ind == 1) %>%
  ggplot(aes(x = µg, y = RMR)) +
  geom_point(size=2.5) +
  theme_minimal(base_size = 20) + xlab("mass (ug)") + ylab("RMR (µLO2/mgmass/hr)")


### finalized data from ASH 13 January 2025 ####

dat <- read_xlsx("./Ostracod Respiration Rates Summary Table 13 Jan.xlsx",sheet = 'Mass Scaling',trim_ws = TRUE)

dat2 <- dat %>% rename(RMR = `RMR (µLO2/mgmass/hr)`,M_adj = `M(adj) µLO2/hr)`) %>%
  mutate(Trial = as.factor(Trial)) %>%
  select(c(Trial,RMR,M_adj,Channel,Mass,ind,night_measured,signalling_rate)) %>%
  drop_na(RMR) %>%
  mutate(Vessel = case_when(ind == 1 ~ "Individual",
                               ind > 1 & ind < 10 ~ "Vial",
                               ind >= 10 ~ "Column"),
         Vessel = factor(Vessel,levels = c("Column","Vial","Individual")),
         paired = case_when(Vessel == "Individual" & c(Trial == 4 | Trial == 5 | Trial == 6 | Trial == 7) ~ TRUE,.default = FALSE),
         day_first = case_when(paired == TRUE & c(Trial == 6 | Trial == 7) ~ TRUE,
                               paired == TRUE & c(Trial == 4 | Trial == 5) ~ FALSE,.default = NA),
  )

## looking at the correlation between mass and the RMR or A measurements ##

p1 <- dat2 %>% filter(ind == 1, night_measured == TRUE) %>%
  ggplot(aes(x = Mass, y = RMR)) +
  geom_point(size=2.5) +
  theme_minimal(base_size = 20) + xlab("mass (ug)") + ylab("RMR (µLO2/mg mass/hr)")

p2 <- dat2 %>% filter(ind == 1, night_measured == TRUE) %>%
  ggplot(aes(x = Mass, y = M_adj)) +
  geom_point(size=2.5) +
  theme_minimal(base_size = 20) + xlab("mass (ug)") + ylab("A ( µL O2/ M(adj)/hr )")

ggarrange(plotlist = c(p1,p2),ncol = 2)

## re-making THO's plot just to see if it falls out as well

dat3 <- dat2 %>% mutate(VesselxTime = case_when(Vessel == "Individual" & night_measured == FALSE & paired == TRUE ~ "Individual Day",
                                       Vessel == "Individual" & night_measured == TRUE & paired == TRUE ~ "Individual Night",
                                       Vessel == "Individual" & paired == FALSE ~ "Individual Unpaired",
                                       .default = Vessel),
                VesselxTime = factor(VesselxTime,levels = c("Column","Vial","Individual Unpaired",
                                                            "Individual Night","Individual Day")),
                pair_id = interaction(Trial, Channel, drop = TRUE),
                day_first = factor(day_first,levels = c(TRUE,FALSE,NA)))

dat3 %>%
  ggplot(aes(x = VesselxTime, y = M_adj)) +
  geom_boxplot(size = 0.5) +
  geom_line(
    data = dat3 %>% filter(paired == TRUE),
    aes(group = pair_id),
    linewidth = 0.6,
    alpha = 0.7
  ) +
  geom_point(size = 3.5,aes(color = day_first)) +
  theme_minimal(base_size = 20) +
  ylab("A ( µL O2/ M(adj)/hr )")

## redo-ing the signalling plot
library(ggpmisc)

dat3 %>%
  ggplot(aes(y = M_adj, x = signalling_rate)) +
  geom_smooth(method = "lm",se = TRUE,color="royalblue3",fill="lightblue3") +
  geom_point(size = 3.5) +
  stat_poly_eq(use_label(c("eq.label", "R2", "p")),
               formula = y ~ x, parse = TRUE,) +
  theme_minimal(base_size = 20) +
  ylab("A ( µL O2/ M(adj)/hr )") +
  xlab("log10 ( # signals per min )") +
  scale_x_log10()


## looking at a random effects model to try and describe some of the variation in A (RMR with M_adj) based on the experimental procedure

ind_data_only <- dat3 %>% filter(Vessel == "Individual") %>%
  mutate(night_measured = factor(night_measured,levels = c(TRUE,FALSE,NA)),
         paired = factor(paired,levels = c(TRUE,FALSE)))

library(lme4)

model_wo_time <- lmer(M_adj ~ night_measured * day_first + (1| pair_id), data = ind_data_only,REML = FALSE)
summary(model_wo_time)
car::Anova(model_wo_time,type="II")

anova(model_wo_time, update(model_wo_time, . ~ . - night_measured:day_first))

library(sjPlot)

sjPlot::plot_model(model_wo_time)

library(emmeans)

emm <- emmeans(model_wo_time, ~ night_measured | day_first)

emm_df <- as.data.frame(emm) %>%
  mutate(
    night_measured = factor(night_measured, levels = levels(ind_data_only$night_measured)),
    night_measured = case_when(night_measured == TRUE ~ "Night",.default = "Day"),
    day_first   = factor(day_first, levels = c(TRUE, FALSE))
  )

ggplot() +
  geom_point(
    data = ind_data_only %>% mutate(night_measured = case_when(night_measured == TRUE ~ "Night",.default = "Day")),
    aes(x = night_measured, y = M_adj, shape = VesselxTime),
    position = position_jitter(width = 0.08),
    alpha = 0.5
  ) +
  geom_point(
    data = emm_df,
    aes(x = night_measured, y = emmean, group = day_first, color = day_first),
    position = position_dodge(width = 0.25),
    size = 3
  ) +
  geom_errorbar(
    data = emm_df,
    aes(x = night_measured, ymin = lower.CL, ymax = upper.CL, group = day_first, color = day_first),
    width = 0.12,
    position = position_dodge(width = 0.25)
  ) +
  geom_line(
    data = emm_df,
    aes(x = night_measured, y = emmean, group = day_first, color = day_first),
    position = position_dodge(width = 0.25)
  ) +
  labs(x = "Time of measurement", y = "A (uL O2 / ug (adj) / hr)\nEMMs (±95% CI)") +
  theme_minimal(base_size = 20)


## checking if the model holds without the unpaired samples ##

ind_data_only <- dat3 %>% filter(Vessel == "Individual" & paired == TRUE) %>%
  mutate(night_measured = factor(night_measured,levels = c(TRUE,FALSE,NA)),
         paired = factor(paired,levels = c(TRUE,FALSE)))

model_wo_time <- lmer(M_adj ~ night_measured * day_first + (1| pair_id), data = ind_data_only,REML = FALSE)
summary(model_wo_time)
car::Anova(model_wo_time,type="II")
