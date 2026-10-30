// CleanWatts mock demo: one household with PV, a battery and appliances.
// Edited live during the demo; see DUMMY-DEMO.md for the story and the
// edits per step, MOCK-DEMO.md for the design.
//
// Attributes marked "configured" are set here and may be edited live.
// Attributes marked "reported" are computed by the simulation every
// simulated hour and read by the battery algorithms' guards.
// All numbers are Real, written with a decimal point (e.g. 19.0, not 19).

package CleanWattsMock {
    private import ScalarValues::*;

    package BatteryCommands {
        action def Standby {}
        action def ChargeFromSolar {}
        action def ChargeFromGrid {}
        action def Discharge {}
        action def ShavePeak {}
    } // package BatteryCommands

    package Devices {
        private import CleanWattsMock::BatteryCommands::*;

        part def Household {
            attribute standbyLoad : Real;     // configured, kW: always-on load (fridge, router, lights)
            attribute netLoad : Real;         // reported, kW: load - PV, before the battery (negative = solar surplus)
            attribute gridImport : Real;      // reported, kW: after the battery (negative = export)
        }

        part def PV {
            attribute pvPeak : Real;          // configured, kWp
            attribute output : Real;          // reported, kW
        }

        part def Grid {
            attribute price : Real;           // reported, EUR/kWh
        }

        part def Battery {
            attribute capacity : Real;        // configured, kWh
            attribute maxPower : Real;        // configured, kW: charge and discharge limit
            attribute reserve : Real;         // configured, 0..1: never discharge below this charge level
            attribute peakLimit : Real;       // configured, kW: PeakShaving keeps grid import below this
            attribute chargePrice : Real;     // configured, EUR/kWh: PriceArbitrage charges at or below this price
            attribute dischargePrice : Real;  // configured, EUR/kWh: PriceArbitrage discharges at or above this price
            attribute soc : Real;             // reported, 0..1: charge level

            perform action standby : Standby;
            perform action chargeFromSolar : ChargeFromSolar;  // charge with the solar surplus
            perform action chargeFromGrid : ChargeFromGrid;    // charge from the grid at maxPower
            perform action discharge : Discharge;              // cover the whole demand
            perform action shavePeak : ShavePeak;              // cover only the demand above peakLimit
        }

        part def WashingMachine {
            attribute power : Real;           // configured, kW
            attribute startHour : Real;       // configured, 0..23
            attribute durationHours : Real;   // configured
            attribute load : Real;            // reported, kW
        }

        // Generic appliance with a fixed cycle, e.g. a dishwasher
        // (CityLearn has no dishwasher class).
        part def DeferrableAppliance {
            attribute power : Real;           // configured, kW
            attribute startHour : Real;       // configured, 0..23
            attribute durationHours : Real;   // configured
            attribute load : Real;            // reported, kW
        }

        part def HeatPump {
            attribute setpoint : Real;        // configured, degrees C
            attribute cop : Real;             // configured: heat out per electricity in
            attribute load : Real;            // reported, kW
        }

        part def Charger {
            attribute chargerPower : Real;    // configured, kW
            attribute chargeStartHour : Real; // configured, 0..23
            attribute durationHours : Real;   // configured
            attribute load : Real;            // reported, kW
        }
    } // package Devices
} // package CleanWattsMock


// The three battery algorithms. All take the same parameters, so switching
// algorithm is a one-word edit of batteryControl's type in Main. Guards read
// netLoad (before the battery), never gridImport (after it): a guard on
// gridImport would make the battery switch back and forth every hour.
package BatteryAlgorithms {
    private import CleanWattsMock::Devices::*;

    // Store the solar surplus, use it whenever the house needs more than
    // the PV produces.
    state def SelfConsumption {
        in battery : Battery;
        in house : Household;
        in grid : Grid;

        entry;
        then Idle;

        state Idle {
            entry battery.standby;
        }
        accept when house.netLoad < 0.0 and battery.soc < 0.95
            then Charging;
        accept when house.netLoad > 0.0 and battery.soc > battery.reserve
            then Discharging;

        state Charging {
            entry battery.chargeFromSolar;
        }
        accept when house.netLoad >= 0.0 or battery.soc >= 0.95
            then Idle;

        state Discharging {
            entry battery.discharge;
        }
        accept when house.netLoad <= 0.0 or battery.soc <= battery.reserve
            then Idle;
    }

    // Store the solar surplus, but only use it to keep grid import below
    // peakLimit.
    state def PeakShaving {
        in battery : Battery;
        in house : Household;
        in grid : Grid;

        entry;
        then Idle;

        state Idle {
            entry battery.standby;
        }
        accept when house.netLoad < 0.0 and battery.soc < 0.95
            then Charging;
        accept when house.netLoad > battery.peakLimit and battery.soc > battery.reserve
            then Discharging;

        state Charging {
            entry battery.chargeFromSolar;
        }
        accept when house.netLoad >= 0.0 or battery.soc >= 0.95
            then Idle;

        state Discharging {
            entry battery.shavePeak;
        }
        accept when house.netLoad <= battery.peakLimit or battery.soc <= battery.reserve
            then Idle;
    }

    // Buy from the grid when cheap, use the stored energy when expensive.
    state def PriceArbitrage {
        in battery : Battery;
        in house : Household;
        in grid : Grid;

        entry;
        then Idle;

        state Idle {
            entry battery.standby;
        }
        accept when grid.price <= battery.chargePrice and battery.soc < 0.95
            then Charging;
        accept when grid.price >= battery.dischargePrice and battery.soc > battery.reserve
            then Discharging;

        state Charging {
            entry battery.chargeFromGrid;
        }
        accept when grid.price > battery.chargePrice or battery.soc >= 0.95
            then Idle;

        state Discharging {
            entry battery.discharge;
        }
        accept when grid.price < battery.dischargePrice or battery.soc <= battery.reserve
            then Idle;
    }
} // package BatteryAlgorithms


package Main {
    private import CleanWattsMock::Devices::*;
    private import BatteryAlgorithms::*;

    // The household owns its devices; the grid is outside it.
    part house1 : Household {
        attribute :>> standbyLoad = 0.6;

        part pv1 : PV {
            attribute :>> pvPeak = 4.0;
        }

        part battery1 : Battery {
            attribute :>> capacity = 10.0;
            attribute :>> maxPower = 4.5;
            attribute :>> reserve = 0.1;
            attribute :>> peakLimit = 4.0;
            attribute :>> chargePrice = 0.07;
            attribute :>> dischargePrice = 0.20;
        }

        part washer1 : WashingMachine {
            attribute :>> power = 2.0;
            attribute :>> startHour = 19.0;
            attribute :>> durationHours = 2.0;
        }

        // Step 2 of the demo: add these two parts (remove the comment markers).
        /*
        part heatPump1 : HeatPump {
            attribute :>> setpoint = 21.0;
            attribute :>> cop = 3.0;
        }

        part evCharger1 : Charger {
            attribute :>> chargerPower = 3.7;
            attribute :>> chargeStartHour = 17.0;
            attribute :>> durationHours = 4.0;
        }
        */
    }

    part grid1 : Grid;

    state batteryControl : SelfConsumption {
        in battery = house1.battery1;
        in house = house1;
        in grid = grid1;
    }
} // package Main
