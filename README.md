# External charge control for Energy Control Wallbox from Heidelberg  
## Main Features
* Consider input from Solar Logger (SolarLog (tm))  
  * Solar Power Output
  * Overall consumption
* Interface to Heidelberg Wallbox
  * Read current charge and connector status
  * Limit current according to charge strategy
* Time limits for on/off/on cycles 
  * Super relevant for PV charge to avoid constant switching between charge/no charge your car
* Supports Hard-Switch via Raspberry GPIO
  * switch between full grid and PV only charge strategy
* Data logging into InfluxDB
* Configuration via .ini config file
  * Max current for overall system (e.g. 16A or 32A) 
  * Min current (e.g. 6A for Heidelberg)

And the best:
* A handful of **working** Unit Tests


