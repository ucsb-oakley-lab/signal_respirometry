
## Generalized consumption_rate.R
## Supports arbitrary channels via CLI args.
## Usage example:
## Rscript consumption_rate.R --csv path/to/file.csv --sal 33 \
##   --control Ch1 --channels Ch2,Ch3,Ch4 \
##   --masses 0.00024,0.00024,0.00024 --vol_control 0.002 \
##   --volumes 0.002,0.002,0.002 --start_hour 1 --end_hour 8 \
##   --microbial_cutoff_hour 5 --out path/to/output

suppressPackageStartupMessages({
	library(readr)
	library(respirometry)
	library(dplyr)
})

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

# Helper to split comma lists
split_commas <- function(x){
	if(is.null(x) || x == "") return(character(0))
	trimws(strsplit(x, ",", fixed = TRUE)[[1]])
}
split_nums <- function(x){
	vals <- split_commas(x)
	as.numeric(vals)
}
parse_bool <- function(x, default=FALSE){
	if(is.null(x)) return(default)
	lx <- tolower(as.character(x))
	if(lx %in% c("1","true","t","yes","y")) return(TRUE)
	if(lx %in% c("0","false","f","no","n")) return(FALSE)
	return(default)
}

csv_path <- if(!is.null(kv$csv)) kv$csv else stop("--csv is required")
out_dir  <- if(!is.null(kv$out)) kv$out else "."
Sal      <- if(!is.null(kv$sal)) as.numeric(kv$sal) else 33
control_channel <- if(!is.null(kv$control)) kv$control else "Ch1"
channels <- split_commas(kv$channels)  # measurement channels excluding control
masses   <- split_nums(kv$masses)      # per measurement channel (same order as channels)
vol_control <- if(!is.null(kv$vol_control)) as.numeric(kv$vol_control) else 0.002
volumes  <- split_nums(kv$volumes)     # per measurement channel
start_hour <- if(!is.null(kv$start_hour)) as.numeric(kv$start_hour) else 1
end_hour   <- if(!is.null(kv$end_hour)) as.numeric(kv$end_hour) else 8
microbial_cutoff_hour <- if(!is.null(kv$microbial_cutoff_hour)) as.numeric(kv$microbial_cutoff_hour) else 5
atm_pres <- if(!is.null(kv$atm_pres)) as.numeric(kv$atm_pres) else 1013.25
mask_channels <- parse_bool(kv$mask_channels, default = FALSE)
cutoff_inclusive <- parse_bool(kv$cutoff_inclusive, default = TRUE)
debug_mode <- parse_bool(kv$debug, default = FALSE)

if(length(channels) == 0) stop("--channels must list at least one channel (excluding control)")
if(length(masses) != length(channels)) stop("--masses count must match --channels count")
if(length(volumes) != length(channels)) stop("--volumes count must match --channels count")

Data <- read.csv(csv_path)
if(!("hours" %in% names(Data))) stop("Data must contain 'hours' column")
if(!("Temp" %in% names(Data))) stop("Data must contain 'Temp' column")

# Verify channel columns exist
all_channels <- c(control_channel, channels)
missing_cols <- setdiff(all_channels, names(Data))
if(length(missing_cols)) stop(paste("Missing channel columns:", paste(missing_cols, collapse = ", ")))

O2_Units <- "kPa"

# Convert all channel O2 to kPa
for(ch in all_channels){
	kpa_col <- paste0(ch, "_kPa")
	Data[[kpa_col]] <- conv_o2(o2 = Data[[ch]], from = "umol_per_l", to = "kPa", temp = Data$Temp, sal = Sal)
}

# Trim data by hours window
trim_data <- subset(Data, hours >= start_hour & hours <= end_hour)
trim_data <- na.omit(trim_data)
if(nrow(trim_data) < 5) stop("Trimmed data has fewer than 5 rows; adjust hour window")

# Duration in minutes from start
eTime_hours <- trim_data$hours
eTime <- (eTime_hours - eTime_hours[1]) * 60
Temp <- median(trim_data$Temp)
DatQ <- rep(TRUE, length(eTime))

# Good data mask for microbial decay exclusion
if(cutoff_inclusive){
	bad_data <- trim_data$hours >= microbial_cutoff_hour
} else {
	bad_data <- trim_data$hours > microbial_cutoff_hour
}

control_kpa <- trim_data[[paste0(control_channel, "_kPa")]]
RMRDmicr <- calc_MO2(duration = eTime, o2 = control_kpa, o2_unit = O2_Units, bin_width = Inf, vol = vol_control, temp = Temp, sal = Sal, good_data = !bad_data)

# Process each measurement channel
results <- list()
debug_rows <- list()

# Optional debug info for control
if(debug_mode){
	total_n <- length(eTime)
	used_idx <- which(!bad_data)
	used_n <- length(used_idx)
	used_hours <- if(used_n>0) trim_data$hours[used_idx] else numeric(0)
	# Compute simple slope in kPa/min for control over used data
	slope_ctrl <- NA_real_
	if(used_n >= 2){
		df_ctrl <- data.frame(x=eTime[used_idx], y=control_kpa[used_idx])
		slope_ctrl <- as.numeric(coef(lm(y ~ x, data=df_ctrl))[2])
	}
	debug_rows[[length(debug_rows)+1]] <- data.frame(
		file = csv_path,
		entity = control_channel,
		role = "control",
		mask_applied = "pre_cutoff",
		cutoff_hour = microbial_cutoff_hour,
		cutoff_inclusive = cutoff_inclusive,
		start_hour_window = min(trim_data$hours),
		end_hour_window = max(trim_data$hours),
		n_total = total_n,
		n_used = used_n,
		used_hour_min = if(length(used_hours)) min(used_hours) else NA_real_,
		used_hour_max = if(length(used_hours)) max(used_hours) else NA_real_,
		slope_kpa_per_min = slope_ctrl,
		MO2_raw_umol_per_hr = NA_real_,
		MO2_control_umol_per_hr = RMRDmicr$MO2,
		MO2_corrected_umol_per_hr = NA_real_,
		mass_g = NA_real_,
		vol_L = vol_control,
		umol_g_hr = NA_real_,
		ml_mg_hr = NA_real_,
		uL_mg_hr = NA_real_,
		stringsAsFactors = FALSE
	)
}
for(i in seq_along(channels)){
	ch <- channels[i]
	vol_ch <- volumes[i]
	mass_ch <- masses[i]
	kpa_series <- trim_data[[paste0(ch, "_kPa")]]
	good_ch <- if(mask_channels) !bad_data else DatQ
	mo2_raw <- calc_MO2(duration = eTime, o2 = kpa_series, o2_unit = O2_Units, bin_width = Inf, vol = vol_ch, temp = Temp, sal = Sal, good_data = good_ch)
	# subtract microbial respiration
	mo2_corrected <- mo2_raw$MO2 - RMRDmicr$MO2
	mo2_mass_specific <- mo2_corrected / mass_ch  # umol / g / hr
	ml_mg_hr <- conv_resp_unit(value = mo2_mass_specific, from = "umol_O2 / g / hr", to = "ml_O2 / mg / hr", temp = Temp, sal = Sal, atm_pres = atm_pres)
	uL_mg_hr <- ml_mg_hr * 1000
	results[[ch]] <- list(umol_g_hr = mo2_mass_specific, ml_mg_hr = ml_mg_hr, uL_mg_hr = uL_mg_hr)

	if(debug_mode){
		# compute simple slope for channel over used data
		total_n <- length(eTime)
		used_idx <- which(good_ch)
		used_n <- length(used_idx)
		used_hours <- if(used_n>0) trim_data$hours[used_idx] else numeric(0)
		slope_ch <- NA_real_
		if(used_n >= 2){
			df_ch <- data.frame(x=eTime[used_idx], y=kpa_series[used_idx])
			slope_ch <- as.numeric(coef(lm(y ~ x, data=df_ch))[2])
		}
		debug_rows[[length(debug_rows)+1]] <- data.frame(
			file = csv_path,
			entity = ch,
			role = "channel",
			mask_applied = if(mask_channels) "pre_cutoff" else "full_window",
			cutoff_hour = microbial_cutoff_hour,
			cutoff_inclusive = cutoff_inclusive,
			start_hour_window = min(trim_data$hours),
			end_hour_window = max(trim_data$hours),
			n_total = total_n,
			n_used = used_n,
			used_hour_min = if(length(used_hours)) min(used_hours) else NA_real_,
			used_hour_max = if(length(used_hours)) max(used_hours) else NA_real_,
			slope_kpa_per_min = slope_ch,
			MO2_raw_umol_per_hr = mo2_raw$MO2,
			MO2_control_umol_per_hr = RMRDmicr$MO2,
			MO2_corrected_umol_per_hr = mo2_corrected,
			mass_g = mass_ch,
			vol_L = vol_ch,
			umol_g_hr = mo2_mass_specific,
			ml_mg_hr = ml_mg_hr,
			uL_mg_hr = uL_mg_hr,
			stringsAsFactors = FALSE
		)
	}
}

# Wide summary
summary <- data.frame(
	file = csv_path,
	temp_C = Temp,
	sal = Sal,
	control_channel = control_channel,
	start_hour = start_hour,
	end_hour = end_hour,
	microbial_cutoff_hour = microbial_cutoff_hour
)
for(ch in channels){
	summary[[paste0(ch, "_umol_g_hr")]] <- results[[ch]]$umol_g_hr
	summary[[paste0(ch, "_ml_mg_hr")]]  <- results[[ch]]$ml_mg_hr
	summary[[paste0(ch, "_uL_mg_hr")]]  <- results[[ch]]$uL_mg_hr
}

if(!dir.exists(out_dir)) dir.create(out_dir, recursive = TRUE)
out_path <- file.path(out_dir, paste0(basename(csv_path), "_R_summary.csv"))
write.csv(summary, out_path, row.names = FALSE)

# Long summary (optional)
long_rows <- do.call(rbind, lapply(channels, function(ch){
	data.frame(
		file = csv_path,
		channel = ch,
		temp_C = Temp,
		sal = Sal,
		umol_g_hr = results[[ch]]$umol_g_hr,
		ml_mg_hr = results[[ch]]$ml_mg_hr,
		uL_mg_hr = results[[ch]]$uL_mg_hr,
		start_hour = start_hour,
		end_hour = end_hour,
		microbial_cutoff_hour = microbial_cutoff_hour,
		stringsAsFactors = FALSE
	)
}))
out_path_long <- file.path(out_dir, paste0(basename(csv_path), "_R_summary_long.csv"))
write.csv(long_rows, out_path_long, row.names = FALSE)

if(debug_mode && length(debug_rows) > 0){
	debug_df <- do.call(rbind, debug_rows)
	out_path_debug <- file.path(out_dir, paste0(basename(csv_path), "_R_debug.csv"))
	write.csv(debug_df, out_path_debug, row.names = FALSE)
}

"Generalized summary written"







