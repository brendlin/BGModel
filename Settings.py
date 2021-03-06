import numpy as np
from collections import OrderedDict
import datetime as dt
import time
import json

#
# This is meant to store a list of settings snapshots, with the day starting from 12am.
# 
#
class UserSetting :

    def __init__(self,_type_of_setting) :

        self.dtype = [('time_seconds',np.int32),('value',np.float64)]
        self.settings_24h = []
        self.type_of_setting = _type_of_setting
        return

    def toJson(self) :
        return json.dumps({'type_of_setting':self.type_of_setting,'settings_24h':self.settings_24h})

    @classmethod
    def fromJson(cls,json_string) :
        the_dict = json.loads(json_string)
        the_class = cls(the_dict['type_of_setting'])

        # convert each to a tuple... sorry this is really gross.
        for setting in the_dict['settings_24h'] :
            hour_by_hour = []
            for setting_at_time_of_day in setting[1] :
                hour_by_hour.append((setting_at_time_of_day[0],setting_at_time_of_day[1]))
            the_class.settings_24h.append([setting[0],hour_by_hour])

        return the_class

    def ToNumpyArray(self,settings_list) :
        return np.array(settings_list, dtype=self.dtype)

    def latestSettingsSnapshot(self) :
        if not self.settings_24h :
            print('warning! No insulin-carb ratio on record!')
        else :
            latest_snapshot = list(self.settings_24h[-1][1])
            return self.ToNumpyArray(latest_snapshot)

        return None

    def getOrMakeSettingsSnapshot_list(self,timestamp) :

        # Get the latest settings snapshot, if it exists
        for setting in self.settings_24h :
            if setting[0] == timestamp :
                return setting[1]

        # If it does not exist, make a new one:
        self.settings_24h.append((timestamp,[]))

        # sort by utc time
        self.settings_24h.sort(key=lambda x: time.mktime(time.strptime(x[0].replace('T',' '), "%Y-%m-%d %H:%M:%S")))

        return self.getOrMakeSettingsSnapshot_list(timestamp)

    def getOrMakeSettingsSnapshot(self,timestamp) :

        return self.ToNumpyArray(self.getOrMakeSettingsSnapshot_list(timestamp))

    def getValidSnapshotAtTime(self,timestamp) :

        the_time = time.mktime(time.strptime(timestamp.replace('T',' '), "%Y-%m-%d %H:%M:%S"))

        for i in range(len(self.settings_24h)-1) :

            iov_0 = time.mktime(time.strptime(self.settings_24h[i][0].replace('T',' '), "%Y-%m-%d %H:%M:%S"))
            iov_1 = time.mktime(time.strptime(self.settings_24h[i+1][0].replace('T',' '), "%Y-%m-%d %H:%M:%S"))

            if (i == 0 and the_time < iov_0) or (the_time >= iov_0 and the_time < iov_1) :
                return self.ToNumpyArray(self.settings_24h[i][1])

        return self.ToNumpyArray(self.settings_24h[-1][1])

    def AddSettingToSnapshot(self,timestamp,timeOfDay_hr,value) :
        # The input, timeOfDay, is in hours (float), starting from MIDNIGHT

        settings_list = self.getOrMakeSettingsSnapshot_list(timestamp)

        timeOfDay_seconds = int(dt.timedelta(hours=timeOfDay_hr).total_seconds())

        index = 0
        if len(settings_list) :
            first,second = zip(*settings_list)
            index = np.searchsorted(first,timeOfDay_seconds,side='right')

        settings_list.insert( index, (timeOfDay_seconds,value) )

        return


    @staticmethod
    def GetSettingAtTime(settings,timeOfDay_hr) :
        # The input, timeOfDay, is in hours (float), starting from midnight

        if not settings.size :
            print('Missing settings.')
            raise AttributeError

        timeOfDay_seconds = int(dt.timedelta(hours=timeOfDay_hr).total_seconds())
        index = np.searchsorted(settings['time_seconds'],timeOfDay_seconds,side='right')

        return settings['value'][index-1]

    def GetLatestSettingAtTime(self,timeOfDay_hr) :
        # The input, timeOfDay, is in hours (float), starting from midnight

        settings = self.latestSettingsSnapshot()
        return UserSetting.GetSettingAtTime(settings,timeOfDay_hr)

#------------------------------------------------------------------

#------------------------------------------------------------------
class TrueUserProfile :

    def __init__(self) :
        #
        # Independent parameters:
        #
        self.binWidth_hr = 0.5
        self.nBins = int( 24 / self.binWidth_hr )
        self.InsulinSensitivity = [0]*self.nBins
        self.FoodSensitivity = [0]*self.nBins # I think I prefer this instead of RCI * Sensitivity
        self.FoodTa = [2.]*self.nBins
        self.InsulinTa = [4.]*self.nBins
        self.LiverHourlyGlucose = [0]*self.nBins # There is going to be a timing offset issue here.

        return

    def toJson(self) :
        return json.dumps({'binWidth_hr':self.binWidth_hr,
                           'nBins':self.nBins,
                           'InsulinSensitivity':self.InsulinSensitivity,
                           'FoodSensitivity':self.FoodSensitivity,
                           'FoodTa':self.FoodTa,
                           'InsulinTa':self.InsulinTa,
                           'LiverHourlyGlucose':self.LiverHourlyGlucose})

    @classmethod
    def fromJson(cls,json_string) :
        the_dict = json.loads(json_string)
        the_class = cls()
        for key in the_dict.keys() :
            setattr(the_class,key,the_dict[key])
        return the_class

    @staticmethod
    def SettingsArrayToList(the_settings_array,outlist) :
        # Something to convert the array into a list
        # input (outlist) is a list with 48 entries

        for i in range(len(outlist)) :
            time_hr = i * 24. / float(len(outlist))
            outlist[i] = UserSetting.GetSettingAtTime(the_settings_array,time_hr)

        return

    def getBin(self,time_ut) :
        # From midnight ... and assuming 48 bins
        return int(time.localtime(time_ut).tm_hour/self.binWidth_hr)

    def getBinFromHourOfDay(self,time_hr) :
        # From midnight ... and assuming 48 bins
        return int( (time_hr%24) /self.binWidth_hr)

    def getInsulinSensitivity(self,time_ut) :
        return self.InsulinSensitivity[self.getBin(time_ut)]

    def getInsulinSensitivityHrMidnight(self,time_hr) :
        return self.InsulinSensitivity[self.getBinFromHourOfDay(time_hr)]

    def getFoodSensitivity(self,time_ut) :
        return self.FoodSensitivity[self.getBin(time_ut)]

    def getFoodSensitivityHrMidnight(self,time_hr) :
        return self.FoodSensitivity[self.getBinFromHourOfDay(time_hr)]

    def setFoodSensitivityHrMidnight(self,time_hr,val) :
        self.FoodSensitivity[self.getBinFromHourOfDay(time_hr)] = val

    def getInsulinTa(self,time_ut) :
        return self.InsulinTa[self.getBin(time_ut)]

    def setInsulinTa(self,val) :
        for i in range(self.nBins) :
            self.InsulinTa[i] = val

    def getInsulinTaHrMidnight(self,time_hr) :
        return self.InsulinTa[self.getBinFromHourOfDay(time_hr)]

    def getFoodTa(self,time_ut) :
        return self.FoodTa[self.getBin(time_ut)]

    def setFoodTa(self,val) :
        for i in range(self.nBins) :
            self.FoodTa[i] = val

    def getFoodTaHrMidnight(self,time_hr) :
        return self.FoodTa[self.getBinFromHourOfDay(time_hr)]

    def getLiverHourlyGlucose(self,time_ut) :
        return self.LiverHourlyGlucose[self.getBin(time_ut)]

    def getLiverHourlyGlucoseHrMidnight(self,time_hr) :
        return self.LiverHourlyGlucose[self.getBinFromHourOfDay(time_hr)]

    def SetInsulinSensitivity(self,time_hr,val) :
        # specify the time starting from midnight!
        self.InsulinSensitivity[self.getBinFromHourOfDay(time_hr)] = val

    def AddSensitivityFromArrays(self,h_insulin,h_ric) :

        self.SettingsArrayToList(h_insulin,self.InsulinSensitivity)

        # We want to save the food sensitivity, not the RIC. Food sensitivity is the independent var.
        tmp_ric = [0]*self.nBins
        self.SettingsArrayToList(h_ric,tmp_ric)
        for i in range(len(tmp_ric)) :
            self.FoodSensitivity[i] = self.InsulinSensitivity[i] / float(tmp_ric[i])

        # Invert the sign of the sensitivity:
        for i in range(len(self.InsulinSensitivity)) :
            self.InsulinSensitivity[i] = -self.InsulinSensitivity[i]

        return

    def AddHourlyGlucoseFromArrays(self,h_basal,h_duration) :

        sensitivity_set = (True in list(a != 0 for a in self.InsulinSensitivity))
        if not sensitivity_set :
            print('Error - tried to make basal glucose, but sensitivity is not set!')
            return

        tmp_basal = [0]*self.nBins
        self.SettingsArrayToList(h_basal,tmp_basal)
        tmp_duration = [0]*self.nBins
        self.SettingsArrayToList(h_duration,tmp_duration)

        # assume that the user was trying to match the glucose from 2 hours in the future.
        for i in range(len(tmp_basal)) :
            # E.g. 4*30 minutes earlier, which sometimes goes to the other end of the array.

            peak_point = tmp_duration[i]/2. # Assume the peak of the basal is Ta/2.
            offset = int( peak_point / float(self.binWidth_hr))

            self.LiverHourlyGlucose[(i+offset)%self.nBins] = - tmp_basal[i] * self.InsulinSensitivity[i]

        return


    def AddDurationFromArray(self,h_duration) :

        self.SettingsArrayToList(h_duration,self.InsulinTa)
        return


    def Print(self) :
        def tmpformat(alist,n=2) :
            return ''.join(('%2.*f'%(n,a)).rjust(6) for a in alist)

        print('Time                           :   ',(' '*8).join([' 12am','____',' 4am','____',' 8am','____',
                                                                  ' 12pm','____',' 4pm','____',' 8pm','____']))
        print('InsulinSensitivity Si (mgdL/u) : ',tmpformat(self.InsulinSensitivity[0::2],0))
        print('                                 ',tmpformat(self.InsulinSensitivity[1::2],0))
        print('FoodSensitivity Sf (mgdL/g)    : ',tmpformat(self.FoodSensitivity[0::2],1))
        print('                                 ',tmpformat(self.FoodSensitivity[1::2],1))
        carb_ratio = list(-self.InsulinSensitivity[i]/float(self.FoodSensitivity[i]) for i in range(self.nBins))
        print('(Carb ratio Si/Sf) (g/u)       : ',tmpformat(carb_ratio[0::2],0))
        print('                                 ',tmpformat(carb_ratio[1::2],0))

        print('InsulinTa (hours)              : ',tmpformat(self.InsulinTa[0::2],1))
        print('                                 ',tmpformat(self.InsulinTa[1::2],1))
        print('FoodTa (hours)                 : ',tmpformat(self.FoodTa[0::2],1))
        print('                                 ',tmpformat(self.FoodTa[1::2],1))

        print('LiverHourlyGlucose (mgdL/hour) : ',tmpformat(self.LiverHourlyGlucose[0::2],0)) # on-the-hour
        print('                                 ',tmpformat(self.LiverHourlyGlucose[1::2],0)) # 30-minute
        return

    def TrueUserProfileToCorrespondingSettings() :
        #
        # For the TrueUserProfile suggested, output the approximate output settings
        #
        # For instance, Basal insulin rate is NOT part of the user profile. But we can
        # translate the user profile to a suggested basal rate.

        pass
