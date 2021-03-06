import math
import time
import datetime

#------------------------------------------------------------------
def InsulinActionCurve(time_hr,Ta) :
    if time_hr < 0 :
        return 0

    result = 1 - math.pow(0.05,math.pow(time_hr/float(Ta),2))
    return result

#------------------------------------------------------------------
def InsulinActionCurveDerivative(time_hr,Ta) :
    if time_hr < 0 :
        return 0

    result = math.log(20)*2*math.pow((1/float(Ta)),2)
    result *= time_hr
    result *= math.pow(0.05,math.pow(time_hr/float(Ta),2))
    return result


#------------------------------------------------------------------
class BGEventBase :
    
    def __init__(self,iov_0_utc,iov_1_utc) :
        self.iov_0_utc = iov_0_utc
        self.iov_1_utc = iov_1_utc
        return

    @staticmethod
    def GetUtcFromString(iov_str) :
        """call via BGEventBase.GetUtcFromString('02/24/2019 12:00:00')"""
        """or       BGEventBase.GetUtcFromString('2019-02-24T12:00:00')"""

        try :
            # Medtronic csv format
            iov_utc = int(time.mktime(time.strptime(iov_str,"%m/%d/%y %H:%M:%S")))
            return iov_utc

        except ValueError :
            pass

        try :
            # Tidepool format
            iov_utc = int(time.mktime(time.strptime(iov_str, '%Y-%m-%dT%H:%M:%S')))
            return iov_utc

        except ValueError :
            pass

        try :
            # Another format
            iov_utc = int(time.mktime(time.strptime(iov_str, '%Y-%m-%d %H:%M:%S')))
            return iov_utc

        except ValueError :
            pass

        print('Error: could not convert to UTC: %s'%(iov_str))
        raise ValueError
        return None

    def Duration_hr(self) :
        return (self.iov_1_utc - self.iov_0_utc)/3600.

    def AffectsBG(self) :
        try :
            return self.affectsBG
        except AttributeError :
            print('Please indicate whether %s affects BG!'%(self.__class__.__name__))

        raise AttributeError

    # Helper functions for figuring out the derived class:
    def IsMeasurement(self) :
        return self.__class__.__name__ == 'BGMeasurement'

    def IsBolus(self) :
        return self.__class__.__name__ == 'InsulinBolus'

    def IsSquareWaveBolus(self) :
        return self.__class__.__name__ == 'SquareWaveBolus'

    def IsDualWaveBolus(self) :
        return self.__class__.__name__ == 'DualWaveBolus'

    def IsFood(self) :
        return self.__class__.__name__ == 'Food'

    def IsBasalGlucose(self) :
        return self.__class__.__name__ == 'LiverBasalGlucose'

    def IsBasalInsulin(self) :
        return self.__class__.__name__ == 'BasalInsulin'

    def IsTempBasal(self) :
        return self.__class__.__name__ == 'TempBasal'

    def IsSuspend(self) :
        return self.__class__.__name__ == 'Suspend'

    def IsExercise(self) :
        return self.__class__.__name__ == 'ExerciseEffect'

    def IsLiverFattyGlucose(self) :
        return self.__class__.__name__ == 'LiverFattyGlucose'

    def IsAnnotation(self) :
        return self.__class__.__name__ == 'Annotation'

#------------------------------------------------------------------
class BGActionBase(BGEventBase) :

    def __init__(self,iov_0_utc,iov_1_utc) :
        BGEventBase.__init__(self,iov_0_utc,iov_1_utc)
        return

    def getTa(self,settings,whichTa) :
        if hasattr(self,'Ta') :
            return self.Ta
        return getattr(settings,whichTa)(self.iov_0_utc)

    def getIntegralBase(self,time_start,time_end,settings,whichTa) :
        # whichTa is a string (either 'getInsulinTa' or 'getFoodTa')

        if time_end < self.iov_0_utc :
            return 0.

        time_hr_start = (time_start - self.iov_0_utc)/3600.
        time_hr_end   = (time_end   - self.iov_0_utc)/3600.

        # Get the appropriate decay time
        Ta = self.getTa(settings,whichTa)

        # Get the magnitude (virtual, must be specified by the derived class)
        magnitude = self.getMagnitudeOfBGEffect(settings)

        return (InsulinActionCurve(time_hr_end,Ta) - InsulinActionCurve(time_hr_start,Ta)) * magnitude


    # The BG equivalent of "Active Insulin"
    def BGEffectRemaining(self,time_ut,settings) :
        
        infinity = time_ut + datetime.timedelta(days=30).total_seconds()

        # getIntegral is virtual, specified in the derived class
        return self.getIntegral(time_ut,infinity,settings)


    # Derivative, useful for making e.g. absorption plots
    def getBGEffectDerivPerHourBase(self,time_ut,settings,whichTa) :

        if (time_ut < self.iov_0_utc) or (time_ut > self.iov_1_utc) :
            return 0.

        time_hr = (time_ut - self.iov_0_utc)/3600.
        Ta = self.getTa(settings,whichTa)

        return InsulinActionCurveDerivative(time_hr,Ta) * self.getMagnitudeOfBGEffect(settings)

    # TODO: just replace this with the integral, no???
    def getBGEffectDerivPerHourTimesInterval(self,time_ut,delta_hr,settings) :
        return self.getBGEffectDerivPerHour(time_ut,settings) * delta_hr
