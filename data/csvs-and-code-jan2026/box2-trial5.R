library(readr)
library(respirometry)
library(dplyr)

#File directory
#setwd("F:/Ostracod Respirometry")

#Data<-read.csv("box2-trial5.csv")
Data<-read.csv("/Users/oakley/Documents/GitHub/signal_respirometry/data/csvs-and-code-jan2026/box2-trial5.csv")

#Salinity
Sal<-33 #Based on Smithsonian surveys of the site

#Dry mass in grams. As example, using Daphnia pulex adult dry mass of 240 ug.The mass number is the channel number.
Mass02<-0.0044
#Mass03<-0.0048
Mass04<-0.0048

#Volume of chamber in L, "micr" will refer to the control/blank chamber. It stands for "microbial respiration."
volmicr<-0.260
vol02<-0.262
#vol03<-0.264
vol04<-0.268

#SMR: Standard metabolic rate, FAS: factorial aerobic scope
SMR<- NULL
FAS<- NULL

Data$Ch1_kPa<-conv_o2(o2 = Data$Ch1, from = "umol_per_l", to = "kPa", temp = Data$Temp, sal = 33)
Data$Ch2_kPa<-conv_o2(o2 = Data$Ch2, from = "umol_per_l", to = "kPa", temp = Data$Temp, sal = 33)
#Data$Ch3_kPa<-conv_o2(o2 = Data$Ch3, from = "umol_per_l", to = "kPa", temp = Data$Temp, sal = 33)
Data$Ch4_kPa<-conv_o2(o2 = Data$Ch4, from = "umol_per_l", to = "kPa", temp = Data$Temp, sal = 33)

#Clarifying that my O2 units will be in kPa
O2_Units<- "kPa"

#Create subset, delimitations by hours column, not particular O2 values
trim_data<-subset(Data, hours>=1 & hours<=8) #After 1h
trim_data <- na.omit(trim_data)

#Time column and recording intervals
eTime<- trim_data[,1]
rec_int<-round(median(eTime[2:length(eTime)]-eTime[1:(length(eTime)-1)]),0)

#Establishing the data from the chambers. Ch1 is control.
RMR_micr<- trim_data[,7]
RMR_02<- trim_data[,8]
#RMR_03<- trim_data[,10]
RMR_04<- trim_data[,9]

DatQ<- rep(TRUE,times=length(eTime))
Temp<- median(trim_data[(DatQ==TRUE),6])  # Column 6 (not 7) because Ch3 is missing from this CSV
eTime<- (eTime - eTime[1])/60

#Plot raw data of oxygen consumption over time
#Can plot this as an example for microbial, which we are expecting to be pretty horizontal: 
#plot(x=eTime[DatQ==TRUE],y=RMR_micr[DatQ==TRUE],ylim=c(15,22),xlab = "eTime (minutes)",ylab = O2_Units, main= "Control")
#plot(x=eTime[DatQ==TRUE],y=RMR_02[DatQ==TRUE],ylim=c(10,20),xlab = "eTime (minutes)",ylab = O2_Units, main= "B2C2")
##plot(x=eTime[DatQ==TRUE],y=RMR_03[DatQ==TRUE],ylim=c(10,20),xlab = "eTime (minutes)",ylab = O2_Units, main= "B2C3")
#plot(x=eTime[DatQ==TRUE],y=RMR_04[DatQ==TRUE],ylim=c(10,20),xlab = "eTime (minutes)",ylab = O2_Units, main= "B2C4")

#Calc MO2 for range
bad_data = trim_data$hours >= 5
RMRDmicr <- calc_MO2(duration = eTime,o2 = RMR_micr, o2_unit = O2_Units, bin_width = Inf, vol=volmicr,temp = Temp, sal = Sal, good_data = !bad_data)

RMRD02 <- calc_MO2(duration = eTime,o2 = RMR_02, o2_unit = O2_Units, bin_width = Inf, vol=vol02,temp = Temp, sal = Sal, good_data = DatQ)

#RMRD03 <- calc_MO2(duration = eTime,o2 = RMR_03, o2_unit = O2_Units, bin_width = Inf, vol=vol03,temp = Temp, sal = Sal, good_data = DatQ)

RMRD04 <- calc_MO2(duration = eTime,o2 = RMR_04, o2_unit = O2_Units, bin_width = Inf, vol=vol04,temp = Temp, sal = Sal, good_data = DatQ)

#Deduct microbial respiration
RMRD02$MO2<-RMRD02$MO2-RMRDmicr$MO2
#RMRD03$MO2<-RMRD03$MO2-RMRDmicr$MO2
RMRD04$MO2<-RMRD04$MO2-RMRDmicr$MO2

#Correct MO2 for mass
RMRD02$MO2_mass_specific<-RMRD02$MO2/Mass02 
#RMRD03$MO2_mass_specific<-RMRD03$MO2/Mass03
RMRD04$MO2_mass_specific<-RMRD04$MO2/Mass04

#If you are getting rmr in seawater, your mass specific rate will be in the RMRD0# dataset, under the column MO2_mass_specific in umol/g/hr.

#B2C2
B2C2<-conv_resp_unit(value=RMRD02$MO2_mass_specific, from="umol_O2 / g / hr", to= "ml_O2 / mg / hr", temp = Temp, sal = Sal, atm_pres = 1013.25)
#B2C3<-conv_resp_unit(value=RMRD03$MO2_mass_specific, from="umol_O2 / g / hr", to= "ml_O2 / mg / hr", temp = Temp, sal = Sal, atm_pres = 1013.25)
B2C4<-conv_resp_unit(value=RMRD04$MO2_mass_specific, from="umol_O2 / g / hr", to= "ml_O2 / mg / hr", temp = Temp, sal = Sal, atm_pres = 1013.25)

#ul/mg/hr
B2C2*1000
#B2C3*1000
B2C4*1000









