
library(readr)
library(respirometry)
library(dplyr)

# --- Simple CLI arg parsing ---
args <- commandArgs(trailingOnly = TRUE)
parse_args <- function(args){
	kv <- list()
	i <- 1
	while(i <= length(args)){
		if(startsWith(args[i], "--")){
			key <- substring(args[i], 3)
			if(i + 1 <= length(args)){
				val <- args[i+1]
				kv[[key]] <- val
			}
			i <- i + 2
		} else {
			i <- i + 1
		}
	}
	kv
}
kv <- parse_args(args)

# Inputs and parameters
csv_path <- if(!is.null(kv$csv)) kv$csv else "/Users/oakley/Documents/GitHub/signal_respirometry/data/original_respirometry_Panama2025/box2-trial1.csv"
out_dir <- if(!is.null(kv$out)) kv$out else "/Users/oakley/Documents/GitHub/signal_respirometry/data/processed"

Sal <- if(!is.null(kv$sal)) as.numeric(kv$sal) else 33
Mass02 <- if(!is.null(kv$mass02)) as.numeric(kv$mass02) else 0.00024
Mass03 <- if(!is.null(kv$mass03)) as.numeric(kv$mass03) else 0.00024
Mass04 <- if(!is.null(kv$mass04)) as.numeric(kv$mass04) else 0.00024
volmicr <- if(!is.null(kv$volmicr)) as.numeric(kv$volmicr) else 0.002
vol02 <- if(!is.null(kv$vol02)) as.numeric(kv$vol02) else 0.002
vol03 <- if(!is.null(kv$vol03)) as.numeric(kv$vol03) else 0.002
vol04 <- if(!is.null(kv$vol04)) as.numeric(kv$vol04) else 0.002

# Load data
Data<-read.csv(csv_path)

#SMR: Standard metabolic rate, FAS: factorial aerobic scope
SMR<- NULL
FAS<- NULL

Data$Ch1_kPa<-conv_o2(o2 = Data$Ch1, from = "umol_per_l", to = "kPa", temp = Data$Temp, sal = Sal)
Data$Ch2_kPa<-conv_o2(o2 = Data$Ch2, from = "umol_per_l", to = "kPa", temp = Data$Temp, sal = Sal)
Data$Ch3_kPa<-conv_o2(o2 = Data$Ch3, from = "umol_per_l", to = "kPa", temp = Data$Temp, sal = Sal)
Data$Ch4_kPa<-conv_o2(o2 = Data$Ch4, from = "umol_per_l", to = "kPa", temp = Data$Temp, sal = Sal)

#Clarifying that my O2 units will be in kPa
O2_Units<- "kPa"

#Create subset, delimitations by seconds column, not particular O2 values
trim_data<-subset(Data,hours>=1 &Data,hours<=8) #After 1h
trim_data <- na.omit(trim_data)

#Time column and recording intervals
eTime<- trim_data[,1]
rec_int<- round(median(eTime[2:length(eTime)]-eTime[1:(length(eTime)-1)]),0)

#Establishing the data from the chambers. Ch1 is control.
RMR_micr<- trim_data[,8]
RMR_02<- trim_data[,9]
RMR_03<- trim_data[,10]
RMR_04<- trim_data[,11]

DatQ<- rep(TRUE,times=length(eTime))
Temp<- median(trim_data[(DatQ==TRUE),7])
eTime<- (eTime - eTime[1])/60

#Plot raw data of oxygen consumption over time
#Can plot this as an example for microbial, which we are expecting to be pretty horizontal: 
plot(x=eTime[DatQ==TRUE],y=RMR_micr[DatQ==TRUE],ylim=c(0,22.5),xlab = "eTime (minutes)",ylab = O2_Units, main= "Control")
plot(x=eTime[DatQ==TRUE],y=RMR_02[DatQ==TRUE],ylim=c(0,21.5),xlab = "eTime (minutes)",ylab = O2_Units, main= "B2C2")
plot(x=eTime[DatQ==TRUE],y=RMR_03[DatQ==TRUE],ylim=c(0,21.5),xlab = "eTime (minutes)",ylab = O2_Units, main= "B2C3")
plot(x=eTime[DatQ==TRUE],y=RMR_04[DatQ==TRUE],ylim=c(0,21.5),xlab = "eTime (minutes)",ylab = O2_Units, main= "B2C4")

#Calc MO2 for range
bad_data = trim_data$hours >= 5
RMRDmicr <- calc_MO2(duration = eTime,o2 = RMR_micr, o2_unit = O2_Units, bin_width = Inf, vol=volmicr,temp = Temp, sal = Sal, good_data = !bad_data)

RMRD02 <- calc_MO2(duration = eTime,o2 = RMR_02, o2_unit = O2_Units, bin_width = Inf, vol=vol02,temp = Temp, sal = Sal, good_data = DatQ)

RMRD03 <- calc_MO2(duration = eTime,o2 = RMR_03, o2_unit = O2_Units, bin_width = Inf, vol=vol03,temp = Temp, sal = Sal, good_data = DatQ)

RMRD04 <- calc_MO2(duration = eTime,o2 = RMR_04, o2_unit = O2_Units, bin_width = Inf, vol=vol04,temp = Temp, sal = Sal, good_data = DatQ)

#Deduct microbial respiration
RMRD02$MO2<-RMRD02$MO2-RMRDmicr$MO2
RMRD03$MO2<-RMRD03$MO2-RMRDmicr$MO2
RMRD04$MO2<-RMRD04$MO2-RMRDmicr$MO2

#Correct MO2 for mass
RMRD02$MO2_mass_specific<-RMRD02$MO2/Mass02 
RMRD03$MO2_mass_specific<-RMRD03$MO2/Mass03
RMRD04$MO2_mass_specific<-RMRD04$MO2/Mass04

#If you are getting rmr in seawater, your mass specific rate will be in the RMRD0# dataset, under the column MO2_mass_specific in umol/g/hr.

"#B2C2"
B2C2<-conv_resp_unit(value=RMRD02$MO2_mass_specific, from="umol_O2 / g / hr", to= "ml_O2 / mg / hr", temp = Temp, sal = Sal, atm_pres = 1013.25)
B2C3<-conv_resp_unit(value=RMRD03$MO2_mass_specific, from="umol_O2 / g / hr", to= "ml_O2 / mg / hr", temp = Temp, sal = Sal, atm_pres = 1013.25)
B2C4<-conv_resp_unit(value=RMRD04$MO2_mass_specific, from="umol_O2 / g / hr", to= "ml_O2 / mg / hr", temp = Temp, sal = Sal, atm_pres = 1013.25)

# Save summary CSV to out_dir
summary <- data.frame(
	file = csv_path,
	temp_C = Temp,
	B2C2_ml_mg_hr = B2C2,
	B2C3_ml_mg_hr = B2C3,
	B2C4_ml_mg_hr = B2C4,
	B2C2_uL_mg_hr = B2C2*1000,
	B2C3_uL_mg_hr = B2C3*1000,
	B2C4_uL_mg_hr = B2C4*1000
)
out_path <- file.path(out_dir, paste0(basename(csv_path), "_R_summary.csv"))
write.csv(summary, out_path, row.names = FALSE)

#ul/mg/hr
B2C2*1000
B2C3*1000
B2C4*1000






