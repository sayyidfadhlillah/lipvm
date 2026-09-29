package CleanWatts {

    private import ScalarValues::*;

    // Singular device slots: one Building has exactly one of each
    // (citylearn.building.Building.__init__: electrical_storage/pv/
    // cooling_storage, each defaulting to a zero-capacity stub if unset).

    part def Battery {
        attribute capacity : Real;
        attribute nominal_power : Real;
    }

    part def PV {
        attribute nominal_power : Real;
    }

    part def StorageTank {
        attribute capacity : Real;
    }

    // List-typed device slots: a Building has zero or more of each
    // (citylearn.building.Building.__init__: electric_vehicle_chargers/
    // deferrable_appliances/escalators, each defaulting to [] if unset).

    part def Charger {
        attribute max_charging_power : Real;
    }

    part def DeferrableAppliance {
        attribute trigger_threshold : Real;
    }

    part def Escalator {
        attribute standby_power : Real;
    }

    part def Building {
        ref electrical_storage : Battery;
        ref pv : PV;
        ref cooling_storage : StorageTank;

        ref electric_vehicle_chargers : Charger[0..*];
        ref deferrable_appliances : DeferrableAppliance[0..*];
        ref escalators : Escalator[0..*];
    }

} // package CleanWatts

package Main {

    private import CleanWatts::*;

    part battery1 : Battery {
        attribute :>> capacity = 10.0;
        attribute :>> nominal_power = 5.0;
    }

    part pv1 : PV {
        attribute :>> nominal_power = 7.5;
    }

    part coolingTank1 : StorageTank {
        attribute :>> capacity = 20.0;
    }

    part charger1 : Charger {
        attribute :>> max_charging_power = 7.4;
    }

    part charger2 : Charger {
        attribute :>> max_charging_power = 11.0;
    }

    part washer1 : DeferrableAppliance {
        attribute :>> trigger_threshold = 0.5;
    }

    part escalator1 : Escalator {
        attribute :>> standby_power = 1.0;
    }

    part building1 : Building {
        :>> electrical_storage = battery1;
        :>> pv = pv1;
        :>> cooling_storage = coolingTank1;

        :>> electric_vehicle_chargers = (charger1, charger2);
        :>> deferrable_appliances = (washer1);
        :>> escalators = (escalator1);
    }

} // package Main
