from .BGBaseClasses import *
from .Settings import *
import datetime as dt

#------------------------------------------------------------------
def findFirstBG(conts) :
    # Quick function to find the first BG
    for c in conts :
        if c.IsMeasurement() and c.firstBG :
            return c
    return None

#------------------------------------------------------------------
class Annotation(BGEventBase) :
    def __init__(self,iov_0_utc,iov_1_utc,annotation) :
        BGEventBase.__init__(self,iov_0_utc,iov_1_utc)
        self.annotation = annotation.replace('\x00','').strip()
        return

#------------------------------------------------------------------
class BGMeasurement(BGEventBase) :
    #
    # BG Reading
    #
    def __init__(self,iov_0_utc,iov_1_utc,const_BG) :
        BGEventBase.__init__(self,iov_0_utc,iov_1_utc)
        self.affectsBG = False
        self.const_BG = const_BG # real BG reading
        self.firstBG = False

    @classmethod
    def FromStringDate(cls,iov_0_str,iov_1_str,const_BG) :
        """call via my_inst = BGMeasurement.FromStringDate('2019-02-24T12:00:00','2019-02-24T12:45:00',175)"""

        iov_0_utc = BGEventBase.GetUtcFromString(iov_0_str)
        iov_1_utc = BGEventBase.GetUtcFromString(iov_1_str)
        return cls(iov_0_utc,iov_1_utc,const_BG)

#------------------------------------------------------------------
class InsulinBolus(BGActionBase) :

    def __init__(self,time_ut,insulin) :
        BGActionBase.__init__(self,time_ut,time_ut + dt.timedelta(hours=6).total_seconds())
        self.affectsBG = True
        self.insulin = insulin
        self.UserInputCarbSensitivity = 2
        self.BWZMatchedDelivered = True
        self.BWZEstimate = 0
        self.BWZInsulinSensitivity = 0
        self.BWZCorrectionEstimate = 0
        self.BWZFoodEstimate       = 0
        self.BWZActiveInsulin      = 0
        self.BWZBGInput            = 0
        self.BWZCarbRatio          = 0

    @classmethod
    def FromStringDate(cls,time_str,insulin) :
        time_utc = BGEventBase.GetUtcFromString(time_str)
        return cls(time_utc,insulin)

    # This used to be called getEffectiveSensitivity, but that name is misleading for food.
    def getMagnitudeOfBGEffect(self,settings) :
        return settings.getInsulinSensitivity(self.iov_0_utc) * self.insulin

    def getIntegral(self,time_start,time_end,settings) :
        return self.getIntegralBase(time_start,time_end,settings,'getInsulinTa')

    # Derivative, useful for making e.g. absorption plots
    def getBGEffectDerivPerHour(self,time_ut,settings) :
        return self.getBGEffectDerivPerHourBase(time_ut,settings,'getInsulinTa')

    def PrintBolus(self) :

        star = ' *' if not self.BWZMatchedDelivered else ''
        decaytime = ' %d hour decay'%(self.UserInputCarbSensitivity) if (self.UserInputCarbSensitivity > 2) else ''
        print('Bolus, %s (input BG: %d mg/dl) (S=%d)'%(time.ctime(self.iov_0_utc),self.BWZBGInput,self.BWZInsulinSensitivity))

        def PrintDetails(title,item,postscript='') :
            print(title + ('%2.1f u;'%(item)).rjust(10)+(' %2.1f mg/dl'%(item*self.BWZInsulinSensitivity)).rjust(15)+(' %2.1f g'%(item*self.BWZCarbRatio)).rjust(10)+postscript)
            return

        PrintDetails('  Total Delivered insulin : ',self.insulin,star)
        PrintDetails('  Total Suggested insulin : ',self.BWZEstimate)
        PrintDetails('             food insulin : ',self.BWZFoodEstimate,decaytime)
        PrintDetails('       correction insulin : ',self.BWZCorrectionEstimate)
        PrintDetails('           active insulin : ',self.BWZActiveInsulin)
        print

        return

#------------------------------------------------------------------
class SquareWaveBolus(BGEventBase) :

    def __init__(self,time_ut,duration_hr,insulin) :
        BGEventBase.__init__(self,time_ut,time_ut + duration_hr + dt.timedelta(hours=6).total_seconds())
        self.affectsBG = True
        self.insulin = insulin
        self.duration_hr = duration_hr
        self.miniBoluses = []

        # Update every 6 minutes...!
        time_step_hr = 0.1

        time_it = time_ut

        while time_it < (time_ut + dt.timedelta(hours=self.duration_hr).total_seconds()) :

            # bolus value is total value divided by number of steps
            bolus_val = self.insulin * time_step_hr / float(self.duration_hr)

            minibolus = InsulinBolus(time_it,bolus_val)
            self.miniBoluses.append(minibolus)
            #print("mini-bolus with %.2f insulin"%(bolus_val))

            # increment by one time step
            time_it += dt.timedelta(hours=time_step_hr).total_seconds()

        return

    @classmethod
    def FromStringDate(cls,time_str,duration_hr,insulin) :
        """call via my_inst = SquareWaveBolus.FromStringDate('2019-02-24T12:00:00',3,4.0)"""

        iov_0_utc = BGEventBase.GetUtcFromString(time_str)
        return cls(iov_0_utc,duration_hr,insulin)

    def getBGEffectDerivPerHourTimesInterval(self,time_start,delta_hr,settings) :
        return sum(c.getBGEffectDerivPerHourTimesInterval(time_start,delta_hr,settings) for c in self.miniBoluses)

    def getBGEffectDerivPerHour(self,time_ut,settings) :
        return sum(c.getBGEffectDerivPerHour(time_ut,settings) for c in self.miniBoluses)

    def getIntegral(self,time_start,time_end,settings) :
        return sum(c.getIntegral(time_start,time_end,settings) for c in self.miniBoluses)

    def BGEffectRemaining(self,time_ut,settings) :
        return sum(c.BGEffectRemaining(time_ut,settings) for c in self.miniBoluses)

    def Print(self) :
        print('Square bolus, %s : Duration %.1fh, %2.1fu\n'%(time.ctime(self.iov_0_utc),self.duration_hr,self.insulin))
        return

#------------------------------------------------------------------
class DualWaveBolus(BGEventBase) :

    def __init__(self,time_ut,duration_hr,insulin_square,insulin_inst) :
        BGEventBase.__init__(self,time_ut,time_ut + duration_hr + dt.timedelta(hours=6).total_seconds())
        self.affectsBG = True
        self.insulin_square = insulin_square
        self.insulin_inst = insulin_inst
        self.duration_hr = duration_hr

        self.square = SquareWaveBolus(time_ut,duration_hr,insulin_square)
        self.inst = InsulinBolus(time_ut,insulin_inst)

    @classmethod
    def FromStringDate(cls,time_str,duration_hr,insulin_square,insulin_inst) :
        """call via my_inst = DualWaveBolus.FromStringDate('2019-02-24T12:00:00',3,4.0)"""

        iov_utc = BGEventBase.GetUtcFromString(time_str)
        return cls(iov_utc,duration_hr,insulin_square,insulin_inst)

    def getBGEffectDerivPerHourTimesInterval(self,time_start,delta_hr,settings) :
        return sum(c.getBGEffectDerivPerHourTimesInterval(time_start,delta_hr,settings) for c in [self.square,self.inst])

    def getBGEffectDerivPerHour(self,time_ut,settings) :
        return sum(c.getBGEffectDerivPerHour(time_ut,settings) for c in [self.square,self.inst])

    def getIntegral(self,time_start,time_end,settings) :
        return sum(c.getIntegral(time_start,time_end,settings) for c in [self.square,self.inst])

#------------------------------------------------------------------
class Food(BGActionBase) :

    def __init__(self,iov_utc,food) :
        BGActionBase.__init__(self,iov_utc,iov_utc + dt.timedelta(hours=6).total_seconds())
        self.affectsBG = True
        self.food = food

        # For eventual suggestions
        self.original_value = food
        self.fattyMeal = False

        return

    @classmethod
    def FromStringDate(cls,time_str,food) :
        """call via my_inst = Food.FromStringDate('2019-02-24T12:00:00',30)"""

        iov_utc = BGEventBase.GetUtcFromString(time_str)
        return cls(iov_utc,food)

    def getMagnitudeOfBGEffect(self,settings) :
        return settings.getFoodSensitivity(self.iov_0_utc) * self.food

    def getIntegral(self,time_start,time_end,settings) :
        # If it has its own tA, then the base class knows to override the settings.
        return self.getIntegralBase(time_start,time_end,settings,'getFoodTa')

    # Derivative, useful for making e.g. absorption plots
    def getBGEffectDerivPerHour(self,time_ut,settings) :
        # If it has its own tA, then the base class knows to override the settings.
        return self.getBGEffectDerivPerHourBase(time_ut,settings,'getFoodTa')

    def AddBGEffect(self,time_start,time_end,settings,added_bgeffect) :
        # convert bgeffect into food
        bgeffect_in_slice = self.getIntegral(time_start,time_end,settings)
        # what factor do you need to scale up to the desired effect?
        factor = (bgeffect_in_slice + added_bgeffect)/float(bgeffect_in_slice)
        self.food = self.food * factor

    def PrintSuggestion(self,settings) :
        # We assume that you hijacked this instance to make a fit, and stored
        # the original in "self.original_value"

        if not hasattr(self,'original_value') :
            return

        if not self.fattyMeal :
            # If below a certain threshold, do not bother.
            if self.food > 0 and abs(self.original_value - self.food)/float(self.food) < 0.1 :
                return

            if abs(self.original_value - self.food) < 5 :
                return

        recommendation = ''
        if self.fattyMeal :
            recommendation += '** '
        recommendation += 'Fitted FOOD'
        recommendation += ' at %s'%(time.ctime(self.iov_0_utc))
        recommendation += ' %d -> %d grams'%(self.original_value,self.food)
        if hasattr(self,'Ta') :
            recommendation += ', Ta = %.2f'%(self.Ta)
        print(recommendation)
        return recommendation

#------------------------------------------------------------------
class LiverBasalGlucose(BGEventBase) :
    # This one is a bit special, since its effect is driven entirely
    # by the setting LiverHourlyGlucose, and it's a PARAMETER OF INTEREST.
    # - It has an "infinite" (or undefined) magnitude
    # - It has no defined start time, so its integral can only be defined between two moments

    def __init__(self) :
        BGEventBase.__init__(self,0,float('inf'))
        self.affectsBG = True
        self.binWidth_hr = 0.25 # granularity of the binning, when calculating.
        self.nBins = int( 24 / self.binWidth_hr )
        self.LiverHourlyGlucoseFine = [0]*self.nBins # Make memory slots, but recalculate each time
        self.smear_hr_pm = 1 # average the rate over plus or minus X hours
        return

    def getBin(self,time_ut) :
        # time of day (in hours, fractional)
        lt = time.localtime(time_ut)
        bin = int( (lt.tm_hour + lt.tm_min/60.)/float(self.binWidth_hr) )
        return bin

    def getSmearedList(self,settings) :
        # First, lengthen the list
        tmp = []
        for BG in settings.LiverHourlyGlucose :
            for j in range(int(settings.binWidth_hr/self.binWidth_hr)) :
                tmp.append(BG)

        # Now, smear it:
        smear_hr_pm = int(self.smear_hr_pm/self.binWidth_hr)
        for i in range(len(tmp)) :
            n = 0
            val = 0
            for j in range(i-smear_hr_pm,i+smear_hr_pm+1) :
                n += 1
                val += tmp[j%(len(tmp))]
            self.LiverHourlyGlucoseFine[i] = val/float(n)

        #print(''.join('%2.1f '%(a) for a in LiverHourlyGlucoseFine))
        return self.LiverHourlyGlucoseFine


    def getIntegral(self,time_start,time_end,settings) :

        tmp_LiverHourlyGlucoseFine = self.getSmearedList(settings)

        sum = 0

        # iterators (both are incremented, to avoid float-to-int errors)
        it_time = time_start
        liver_bin = self.getBin(it_time)

        tmp = time.localtime(time_start)
        time_start_day = time_start - tmp.tm_sec - 60*tmp.tm_min - 3600*tmp.tm_hour

        # print('Getting integral for',time.ctime(time_start),time.ctime(time_end))

        # Go through times up to the end, plus one bin width (in order to avoid missing the last bin)
        while (it_time <= time_end + dt.timedelta(hours=self.binWidth_hr).total_seconds()) :

            # For each bin, find the valid time interval (in hours)
            # This should ensure that the final bin is treated correctly.
            low_edge = max(time_start,time_start_day + liver_bin    *dt.timedelta(hours=self.binWidth_hr).total_seconds() )
            up_edge  = min(time_end  ,time_start_day + (liver_bin+1)*dt.timedelta(hours=self.binWidth_hr).total_seconds() )

            if up_edge < low_edge :
                break

            delta_time_hr = (up_edge - low_edge)/3600.
            # print('bin edges:',time.ctime(time_start_day + liver_bin    *self.binWidth_hr*3600.))
            # print(             time.ctime(time_start_day + (liver_bin+1)*self.binWidth_hr*3600.))
            # print(time.ctime(low_edge), time.ctime(up_edge), delta_time_hr)

            # return (Glucose / hour) * D(hour)
            sum += delta_time_hr * tmp_LiverHourlyGlucoseFine[liver_bin % self.nBins]

            it_time += self.binWidth_hr*3600.
            liver_bin += 1

        return sum

    def BGEffectRemaining(self,the_time,settings) :
        return 0

    def getBGEffectDerivPerHourTimesInterval(self,time_start,delta_hr,settings) :

        # Yeah this is really just the integral.
        return self.getIntegral(time_start,time_start + delta_hr*3600.,settings)

    def getBGEffectDerivPerHour(self,time_ut,settings) :

        # just a wrapper for the true user setting
        #return settings.getLiverHourlyGlucose(time_ut)

        # Same, but for the smeared list:
        return self.getSmearedList(settings)[self.getBin(time_ut)]

#------------------------------------------------------------------
class BasalInsulin(BGEventBase) :
    # This is driven by the basal settings, but it is NOT a parameter of interest, it is a known
    # quantity. But it has some similarities to LiverBasalGlucose:
    # - It has an "infinite" (or undefined) magnitude
    # - It has no defined start time, so its integral can only be defined between two moments

    def getBin(self,time_ut) :
        # From 4am ... and assuming 48 bins
        return int(2 * (time.localtime(time_ut).tm_hour + time.localtime(time_ut).tm_min/60.) )

    def __init__(self,iov_0_utc,iov_1_utc,basal_rates,sensitivities=None,containers=[]) :
        BGEventBase.__init__(self,iov_0_utc,iov_1_utc)
        self.affectsBG = True
        self.BasalRates = [0]*48
        TrueUserProfile.SettingsArrayToList(basal_rates,self.BasalRates)

        # Insulin sensitivity is needed to make liver events
        tmp_InsulinSensitivityList = [0]*48
        if type(sensitivities) == type(np.array([])) :
            TrueUserProfile.SettingsArrayToList(sensitivities,tmp_InsulinSensitivityList)
        elif type(sensitivities) == type([]) :
            tmp_InsulinSensitivityList = sensitivities


        self.basalBoluses = []

        # Rounded down to the nearest hour:
        time_ut = iov_0_utc - 60*time.localtime(iov_0_utc).tm_min - time.localtime(iov_0_utc).tm_sec

        # Update every 6 minutes...!
        time_step_hr = 0.1

        fattyEvents = dict()

        while time_ut < iov_1_utc :

            basalFactor = 1
            bolus_val = self.BasalRates[self.getBin(time_ut)]*float(time_step_hr)*basalFactor
            insulin_sensi = tmp_InsulinSensitivityList[self.getBin(time_ut)]

            # If there is a TempBasal, then modify the basalFactor
            for c in containers :
                if not c.IsTempBasal() :
                    continue

                if c.iov_0_utc > time_ut or time_ut > c.iov_1_utc :
                    continue

                basalFactor = c.basalFactor

                # If the basalFactor >1, then
                # Make a new LiverFattyGlucose object, add it to container list
                if basalFactor > 1 :
                    bolusSlice = -insulin_sensi*bolus_val*(basalFactor-1)

                    if c.iov_0_utc not in fattyEvents.keys() :
                        Ta_tempBasal = (c.iov_1_utc - c.iov_0_utc) / float(3600.)
                        fattyEvents[c.iov_0_utc] = {'iov_0_utc':c.iov_0_utc,'iov_1_utc':c.iov_1_utc}
                        fattyEvents[c.iov_0_utc]['BGEffect'] = bolusSlice
                        fattyEvents[c.iov_0_utc]['Ta_tempBasal'] = Ta_tempBasal
                        fattyEvents[c.iov_0_utc]['fractionOfBasal'] = basalFactor-1
                    else :
                        fattyEvents[c.iov_0_utc]['BGEffect'] += bolusSlice

            # Now check for Suspend, which should preempt TempBasals
            for c in containers :
                if not c.IsSuspend() :
                    continue
                if c.iov_0_utc < time_ut and time_ut < c.iov_1_utc :
                    basalFactor = c.basalFactor

            # Finally, make the mini-bolus for the basal insulin.
            bolus_val *= basalFactor
            minibolus = InsulinBolus(time_ut,bolus_val)
            self.basalBoluses.append(minibolus)

            time_ut += time_step_hr*3600.

        for k in fattyEvents.keys() :
            fe = fattyEvents[k]
            fattyEvent = LiverFattyGlucose(fe['iov_0_utc'],fe['iov_1_utc'],fe['BGEffect'],fe['Ta_tempBasal'],fe['fractionOfBasal'])
            fattyEvent.Print()
            containers.append(fattyEvent)

        return

    @classmethod
    def FromStringDate(cls,iov_0_str,iov_1_str,basal_rates,sensitivities=[],containers=[]) :

        iov_0_utc = BGEventBase.GetUtcFromString(iov_0_str)
        iov_1_utc = BGEventBase.GetUtcFromString(iov_1_str)

        return cls(iov_0_utc,iov_1_utc,basal_rates,sensitivities,containers)

    def getBGEffectDerivPerHourTimesInterval(self,time_start,delta_hr,settings) :
        return sum(c.getBGEffectDerivPerHourTimesInterval(time_start,delta_hr,settings) for c in self.basalBoluses)

    def getBGEffectDerivPerHour(self,time_ut,settings) :
        return sum(c.getBGEffectDerivPerHour(time_ut,settings) for c in self.basalBoluses)

    def getIntegral(self,time_start,time_end,settings) :
        return sum(c.getIntegral(time_start,time_end,settings) for c in self.basalBoluses)

    def BGEffectRemaining(self,the_time,settings) :
        return 0

#------------------------------------------------------------------
class TempBasal(BGEventBase) :

    # This class is designed to communicate with the BasalInsulin class.

    def __init__(self,iov_0_utc,iov_1_utc,basalFactor) :
        BGEventBase.__init__(self,iov_0_utc,iov_1_utc)
        self.affectsBG = False

        # value in % (e.g. 100% is the nominal)
        self.basalFactor = basalFactor

    @classmethod
    def FromStringDate(cls,iov_0_str,iov_1_str,basalFactor) :

        iov_0_utc = BGEventBase.GetUtcFromString(iov_0_str)
        iov_1_utc = BGEventBase.GetUtcFromString(iov_1_str)

        return cls(iov_0_utc,iov_1_utc,basalFactor)


#------------------------------------------------------------------
class Suspend(TempBasal) :

    # Very similar to TempBasal, except that we need a different class
    # because Suspend takes precedence over TempBasal

    def __init__(self,iov_0_utc,iov_1_utc) :
        TempBasal.__init__(self,iov_0_utc,iov_1_utc,0)
        self.affectsBG = False

    @classmethod
    def FromStringDate(cls,iov_0_str,iov_1_str) :

        iov_0_utc = BGEventBase.GetUtcFromString(iov_0_str)
        iov_1_utc = BGEventBase.GetUtcFromString(iov_1_str)

        return cls(iov_0_utc,iov_1_utc)

#------------------------------------------------------------------
class LiverFattyGlucose(BGActionBase) :
    #
    # This assumes that the independent variable that the user keeps track of
    # is simply "BG Effect". In other words, we will not attempt any tricky transformation
    # to insulin or food or something.

    def __init__(self,time_start,time_end,BGEffect,Ta_tempBasal,fractionOfBasal) :
        BGActionBase.__init__(self,time_start,time_end + 6.*3600.)
        self.affectsBG = True

        # We keep track of this only in terms of BG effect.
        # When created, this comes from the insulin * sensitivity. But then it becomes
        # a non-associated object (i.e. not dependent on any settings).
        # If a mis-bolus is made, then the magnitude of the mis-bolus is calculated in BG points,
        # and then translated back to insulin via the sensitivity setting.
        self.BGEffect = BGEffect

        # For eventual suggestions
        self.original_value = BGEffect
        self.fractionOfBasal = fractionOfBasal

        # It also has its own Ta
        # This is tunable (1.4 works ok for a 6-hr basal)
        self.Ta_tempBasal = Ta_tempBasal
        self.Ta = Ta_tempBasal * 1.4

        return

    def getFattyGlucoseLocalTa(self,time_ut) :
        return self.Ta

    def getMagnitudeOfBGEffect(self,settings) :
        # settings is not used
        return self.BGEffect

    def getIntegral(self,time_start,time_end,settings) :

        # Use a trick below: instead of settings, give them self (for Ta)
        return self.getIntegralBase(time_start,time_end,self,'getFattyGlucoseLocalTa')


    # Derivative, useful for making e.g. absorption plots
    def getBGEffectDerivPerHour(self,time_ut,settings) :

        # Use a trick below: instead of settings, give them self (for Ta)
        return self.getBGEffectDerivPerHourBase(time_ut,self,'getFattyGlucoseLocalTa')

    def AddBGEffect(self,time_start,time_end,settings,added_bgeffect) :
        # add a bgeffect (in a given time slice)
        bgeffect_in_slice = self.getIntegral(time_start,time_end,settings)
        factor = (bgeffect_in_slice + added_bgeffect)/float(bgeffect_in_slice)
        self.BGEffect = self.BGEffect * factor

    def Print(self) :
        cout = 'LiverFattyGlucose:'
        cout += ' %s -'%(time.ctime(self.iov_0_utc))
        cout += ' %s,' %(time.ctime(self.iov_1_utc))
        bg = ('%.0f'%(self.BGEffect)).rjust(3)
        cout += ' BGEffect: %s mg/dL, lifetime: %2.1f'%(bg,self.Ta)
        print(cout + '\n')
        return

    def PrintSuggestion(self,settings) :
        # We assume that you hijacked this instance to make a fit, and stored
        # the original in "self.original_value"

        if not hasattr(self,'original_value') :
            return

        # If below a certain threshold, do not bother.
        if abs(self.original_value - self.BGEffect)/float(self.BGEffect) < 0.1 :
            return

        Sfood = float(settings.getFoodSensitivity(self.iov_0_utc))
        tempBasal_old = 100*(1 + self.fractionOfBasal)
        tempBasal_new = 100*(1 + (self.fractionOfBasal * self.BGEffect/float(self.original_value) ) )
        recommendation = '** Recommend TEMP BASAL'
        recommendation += ' at %s'%(time.ctime(self.iov_0_utc))
        recommendation += ' %d -> %d mgdL'%(self.original_value,self.BGEffect)
        recommendation += ' (%d -> %d grams)'%(self.original_value/Sfood,self.BGEffect/Sfood)
        recommendation += ' (%d%% -> %d%% for %.2f hours)'%(tempBasal_old,tempBasal_new,self.Ta_tempBasal)
        print(recommendation)
        return recommendation

#------------------------------------------------------------------
class ExerciseEffect(BGEventBase) :
    #
    # This will calculate the "multiplier effect" that exercise has on insulin,
    # and its effect is the sum of those effects.
    #
    def __init__(self,iov_0_utc,iov_1_utc,factor,containers=[]) :
        BGEventBase.__init__(self,iov_0_utc,iov_1_utc)
        self.affectsBG = True
        self.factor = factor
        self.affectedEvents = []
        if len(containers) :
            self.LoadContainers(containers)
        return

    def LoadContainers(self,containers) :
        for c in containers :
            if c.iov_0_utc > self.iov_1_utc :
                continue

            if c.iov_1_utc < self.iov_0_utc :
                continue

            # Consider only insulin
            if not (c.IsBasalInsulin() or c.IsBolus()) :
                continue

            self.affectedEvents.append(c)

        return

    def BGEffectRemaining(self,the_time,settings) :
        return 0

    def getMagnitudeOfBGEffect(self,settings) :
        mag = 0

        time_step = self.iov_0_utc
        hours_per_step = 0.1

        while time_step < self.iov_1_utc :

            for c in self.affectedEvents :
                mag += c.getBGEffectDerivPerHourTimesInterval(time_step,hours_per_step,settings)

            time_step += dt.timedelta(hours=hours_per_step).total_seconds()

        return mag * self.factor

    def getBGEffectDerivPerHour(self,time_ut,settings) :
        deriv = 0
        if self.iov_0_utc > time_ut or time_ut > self.iov_1_utc :
            return 0

        for c in self.affectedEvents :
            deriv += c.getBGEffectDerivPerHour(time_ut,settings)

        return deriv * self.factor

    def getBGEffectDerivPerHourTimesInterval(self,time_start,delta_hr,settings) :
        ret = 0
        if self.iov_0_utc > time_start or time_start > self.iov_1_utc :
            return 0

        for c in self.affectedEvents :
            ret += c.getBGEffectDerivPerHourTimesInterval(time_start,delta_hr,settings)

        return ret * self.factor

    def getIntegral(self,time_start,time_end,settings) :

        ret = 0
        if self.iov_0_utc > time_start or time_end > self.iov_1_utc :
            return 0

        for c in self.affectedEvents :
            ret += c.getIntegral(time_start,time_end,settings)

        return ret * self.factor
