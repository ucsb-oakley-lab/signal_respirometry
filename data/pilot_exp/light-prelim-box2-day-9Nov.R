library(readr)
library(respirometry)
library(dplyr)

#File directory
setwd("F:/Ostracod Respirometry/Prelim data")

Data<-read.csv("light-prelim-box2-day-9Nov.csv")

#Salinity
Sal<-33 #Based on Smithsonian surveys of the site

#Dry mass in grams. The mass number is the channel number.
Mass01<-0.00025
Mass02<-0.00025
Mass03<-0.00025
Mass04<-0.00025

#Volume of chamber in L.
vol01<-0.002
vol02<-0.002
vol03<-0.002
vol04<-0.002

#SMR: Standard metabolic rate, FAS: factorial aerobic scope
SMR<- NULL
FAS<- NULL

Data$Ch1_kPa<-conv_o2(o2 = Data$Ch1, from = "umol_per_l", to = "kPa", temp = Data$Temp, sal = 33)
Data$Ch2_kPa<-conv_o2(o2 = Data$Ch2, from = "umol_per_l", to = "kPa", temp = Data$Temp, sal = 33)
Data$Ch3_kPa<-conv_o2(o2 = Data$Ch3, from = "umol_per_l", to = "kPa", temp = Data$Temp, sal = 33)
Data$Ch4_kPa<-conv_o2(o2 = Data$Ch4, from = "umol_per_l", to = "kPa", temp = Data$Temp, sal = 33)

#Clarifying that my O2 units will be in kPa
O2_Units<- "kPa"

#Create subset, delimitations by hours column, not particular O2 values
trim_data<-subset(Data, hours>=1) #After 1h
trim_data <- na.omit(trim_data)

#Time column and recording intervals
eTime<- trim_data[,1]
rec_int<- round(median(eTime[2:length(eTime)]-eTime[1:(length(eTime)-1)]),0)

#Establishing the data from the chambers.
RMR_01<- trim_data[,"Ch1_kPa"]
RMR_02<- trim_data[,"Ch2_kPa"]
RMR_03<- trim_data[,"Ch3_kPa"]
RMR_04<- trim_data[,"Ch4_kPa"]

DatQ<- rep(TRUE,times=length(eTime))
Temp<- median(trim_data[(DatQ==TRUE),"Temp"])
eTime<- (eTime - eTime[1])/60

#Plot raw data of oxygen consumption over time
#Can plot this as an example for microbial, which we are expecting to be pretty horizontal: 
plot(x=eTime[DatQ==TRUE],y=RMR_01[DatQ==TRUE],ylim=c(19,20.5),xlab = "eTime (minutes)",ylab = O2_Units, main= "Ch1")
plot(x=eTime[DatQ==TRUE],y=RMR_02[DatQ==TRUE],ylim=c(18.5,21.5),xlab = "eTime (minutes)",ylab = O2_Units, main= "Ch2")
plot(x=eTime[DatQ==TRUE],y=RMR_03[DatQ==TRUE],ylim=c(19,21.5),xlab = "eTime (minutes)",ylab = O2_Units, main= "Ch3")
plot(x=eTime[DatQ==TRUE],y=RMR_04[DatQ==TRUE],ylim=c(17,20),xlab = "eTime (minutes)",ylab = O2_Units, main= "Ch4")

#Calc MO2 for range
RMRD01 <- calc_MO2(duration = eTime,o2 = RMR_01, o2_unit = O2_Units, bin_width = Inf, vol=vol01,temp = Temp, sal = Sal, good_data = DatQ)

RMRD02 <- calc_MO2(duration = eTime,o2 = RMR_02, o2_unit = O2_Units, bin_width = Inf, vol=vol02,temp = Temp, sal = Sal, good_data = DatQ)

RMRD03 <- calc_MO2(duration = eTime,o2 = RMR_03, o2_unit = O2_Units, bin_width = Inf, vol=vol03,temp = Temp, sal = Sal, good_data = DatQ)

RMRD04 <- calc_MO2(duration = eTime,o2 = RMR_04, o2_unit = O2_Units, bin_width = Inf, vol=vol04,temp = Temp, sal = Sal, good_data = DatQ)

#Correct MO2 for mass
RMRD01$MO2_mass_specific<-RMRD01$MO2/Mass01
RMRD02$MO2_mass_specific<-RMRD02$MO2/Mass02 
RMRD03$MO2_mass_specific<-RMRD03$MO2/Mass03
RMRD04$MO2_mass_specific<-RMRD04$MO2/Mass04

#If you are getting rmr in seawater, your mass specific rate will be in the RMRD0# dataset, under the column MO2_mass_specific in umol/g/hr.

#Box 2
Ch1_day<-conv_resp_unit(value=RMRD01$MO2_mass_specific, from="umol_O2 / g / hr", to= "ml_O2 / mg / hr", temp = Temp, sal = Sal, atm_pres = 1013.25)
Ch2_day<-conv_resp_unit(value=RMRD02$MO2_mass_specific, from="umol_O2 / g / hr", to= "ml_O2 / mg / hr", temp = Temp, sal = Sal, atm_pres = 1013.25)
Ch3_day<-conv_resp_unit(value=RMRD03$MO2_mass_specific, from="umol_O2 / g / hr", to= "ml_O2 / mg / hr", temp = Temp, sal = Sal, atm_pres = 1013.25)
Ch4_day<-conv_resp_unit(value=RMRD04$MO2_mass_specific, from="umol_O2 / g / hr", to= "ml_O2 / mg / hr", temp = Temp, sal = Sal, atm_pres = 1013.25)

#ul/mg/hr
Ch1_day*1000
Ch2_day*1000
Ch3_day*1000
Ch4_day*1000







