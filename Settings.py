import ROOT
from TimeClass import MyTime

#
# This is meant to store a list of settings histograms, with the day starting from 4am.
# 
#
class SettingsHistograms :

    def __init__(self,_type_of_hist) :
        self.hist_list = []
        self.type_of_hist = _type_of_hist
        return

    def latestHistogram(self) :
        if not self.hist_list :
            print 'warning! No insulin-carb ratio on record!'
        else :
            return self.hist_list[-1]

        return None

    def getOrMakeHistogram(self,histo_tag) :

        # Get the latest histogram, if it exists
        for hist in self.hist_list :
            if histo_tag in hist.GetName() :
                return hist

        # If it does not exist, make a new one:
        # They are all half-hour increments, starting from 4am!
        hist = ROOT.TH1F('%s %s'%(self.type_of_hist,histo_tag),histo_tag,48,0,24)
        hist.SetDirectory(0)

        # append the new histogram to the list
        self.hist_list.append(hist)

        return hist


    def WriteToFile(self,rootfile) :

        if not rootfile :
            return

        def HistsAreIdentical(h1,h2) :
            identical = True
            for i in range(h1.GetNbinsX()+2) :
                if h1.GetBinContent(i) != h2.GetBinContent(i) :
                    identical = False
            return identical

        for i in range(len(self.hist_list)) :
            if not i :
                continue
            if HistsAreIdentical(self.hist_list[i],self.hist_list[i-1]) :
                self.hist_list[i].SetTitle('skip')

        for i in reversed(self.hist_list) :
            if i.GetTitle() == 'skip' :
                continue
            rootfile.cd()
            i.Write()
        return


    def ReadFromFile(self,rootfile) :

        if not rootfile :
            return

        self.hist_list = []

        # Reverse the order in order for the latest histogram to be in the last position.
        for i in reversed(rootfile.GetListOfKeys()) :

            if self.type_of_hist not in i.GetName() :
                continue

            self.hist_list.append(i.ReadObj())

        return


    def AddSettingToHistogram(self,histo_tag,timeOfDay_midnight,value) :
        # The input, timeOfDay, is in hours (float), starting from MIDNIGHT
        # but it will be CONVERTED to 4am

        hist = self.getOrMakeHistogram(histo_tag)

        # hour -> half hour increments
        timeOfDay_midnight = int(2*timeOfDay_midnight)

        # half hour increments, 12am to 4am start time conversion:
        timeOfDay = timeOfDay_midnight - 8 

        # Roll pre-4am to the end of the histogram.
        if timeOfDay < 0 :
            timeOfDay = timeOfDay + 48 # half hour increments

        hist.SetBinContent(timeOfDay+1,value)
        return


    def GetSettingFromHistogram(self,timeOfDay) :
        # The input, timeOfDay, is in hours (float), starting from 4am
        # convert to bins - because these histograms go from 0 to 24.

        hist = self.latestHistogram()

        if not hist :
            'Missing histogram - exiting.'
            import sys; sys.exit;

        iterator = 0.
        while True :
            bin = hist.FindBin(timeOfDay-iterator)
            if bin == 0 :
                iterator -= 24

            # Both the input and the histogram start from 4am.
            result = hist.GetBinContent(bin)
            #print 'timeOfDay:',timeOfDay,'iterator:',iterator,'bin:',hist.FindBin(timeOfDay-iterator),'result:',result

            # Return a non-zero result.
            if result > 0 :
                return result

            # If a result is zero, look back another half hour...
            iterator += 0.5

        return 0

#------------------------------------------------------------------
def HistToList(hist,outlist) :
    # Something to convert the histo into a list
    # input (outlist) is a list with 48 entries

    # Convert the histogram to a fully-populated list
    first_not_empty = [1] + list( range(hist.GetNbinsX(),1,-1) )

    for i in first_not_empty :
        bc = hist.GetBinContent(i)
        if bc == 0 :
            continue
        outlist[0] = bc
        break

    # subsequent bins
    for i in range(hist.GetNbinsX()) :
        if i == 0 :
            continue
        bc = hist.GetBinContent(i+1)
        outlist[i] = bc if (bc != 0) else outlist[i-1]

    return


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

    def getBin(self,time_ut) :
        # From 4am ... and assuming 48 bins
        return int(MyTime.GetTimeOfDay(time_ut)/self.binWidth_hr)

    def getBinFromHourOfDayFromMidnight(self,time_hr) :
        # From midnight ... and assuming 48 bins
        return int( ((time_hr-4)%24) /self.binWidth_hr)

    def getInsulinSensitivity(self,time_ut) :
        return self.InsulinSensitivity[self.getBin(time_ut)]

    def getFoodSensitivity(self,time_ut) :
        return self.FoodSensitivity[self.getBin(time_ut)]

    def getFoodSensitivityHrMidnight(self,hr_fromMidnight) :
        return self.FoodSensitivity[self.getBinFromHourOfDayFromMidnight(hr_fromMidnight)]

    def setFoodSensitivityHrMidnight(self,hr_fromMidnight,val) :
        self.FoodSensitivity[self.getBinFromHourOfDayFromMidnight(hr_fromMidnight)] = val

    def getInsulinTa(self,time_ut) :
        return self.InsulinTa[self.getBin(time_ut)]

    def getFoodTa(self,time_ut) :
        return self.FoodTa[self.getBin(time_ut)]

    def getLiverHourlyGlucose(self,time_ut) :
        return self.LiverHourlyGlucose[self.getBin(time_ut)]

    def SetInsulinSensitivity(self,time_hr,val) :
        # specify the time starting from midnight!
        self.InsulinSensitivity[self.getBinFromHourOfDayFromMidnight(time_hr)] = val

    def AddSensitivityFromHistograms(self,h_insulin,h_ric) :

        HistToList(h_insulin,self.InsulinSensitivity)

        # We want to save the food sensitivity, not the RIC. Food sensitivity is the independent var.
        tmp_ric = [0]*self.nBins
        HistToList(h_ric,tmp_ric)
        for i in range(len(tmp_ric)) :
            self.FoodSensitivity[i] = self.InsulinSensitivity[i] / float(tmp_ric[i])

        # Invert the sign of the sensitivity:
        for i in range(len(self.InsulinSensitivity)) :
            self.InsulinSensitivity[i] = -self.InsulinSensitivity[i]

        return

    def AddHourlyGlucoseFromHistogram(self,h_basal,h_duration) :

        tmp_basal = [0]*self.nBins
        HistToList(h_basal,tmp_basal)
        tmp_duration = [0]*self.nBins
        HistToList(h_duration,tmp_duration)

        # assume that the user was trying to match the glucose from 2 hours in the future.
        for i in range(len(tmp_basal)) :
            # E.g. 4*30 minutes earlier, which sometimes goes to the other end of the histo.

            peak_point = tmp_duration[i]/2. # Assume the peak of the basal is Ta/2.
            offset = int( peak_point / float(self.binWidth_hr))

            self.LiverHourlyGlucose[(i+offset)%self.nBins] = - tmp_basal[i] * self.InsulinSensitivity[i]

        return


    def AddDurationFromHistogram(self,h_duration) :

        HistToList(h_duration,self.InsulinTa)
        return


    def Print(self) :
        def tmpformat(alist,n=2) :
            return ''.join(('%2.*f'%(n,a)).rjust(6) for a in alist)

        print 'Time                           :   ',(' '*8).join([' 4am','____',' 8am','____','12am','____',
                                                                  ' 4pm','____',' 8pm','____','12pm','____'])
        print 'InsulinSensitivity Si (mgdL/u) : ',tmpformat(self.InsulinSensitivity[0::2],0)
        print '                                 ',tmpformat(self.InsulinSensitivity[1::2],0)
        print 'FoodSensitivity Sf (mgdL/g)    : ',tmpformat(self.FoodSensitivity[0::2],1)
        print '                                 ',tmpformat(self.FoodSensitivity[1::2],1)
        carb_ratio = list(-self.InsulinSensitivity[i]/float(self.FoodSensitivity[i]) for i in range(self.nBins))
        print '(Carb ratio Si/Sf) (g/u)       : ',tmpformat(carb_ratio[0::2],0)
        print '                                 ',tmpformat(carb_ratio[1::2],0)

        print 'InsulinTa (hours)              : ',tmpformat(self.InsulinTa[0::2],1)
        print '                                 ',tmpformat(self.InsulinTa[1::2],1)
        print 'FoodTa (hours)                 : ',tmpformat(self.FoodTa[0::2],1)
        print '                                 ',tmpformat(self.FoodTa[1::2],1)

        print 'LiverHourlyGlucose (mgdL/hour) : ',tmpformat(self.LiverHourlyGlucose[0::2],0) # on-the-hour
        print '                                 ',tmpformat(self.LiverHourlyGlucose[1::2],0) # 30-minute
        return

    def TrueUserProfileToCorrespondingSettings() :
        #
        # For the TrueUserProfile suggested, output the approximate output settings
        #
        # For instance, Basal insulin rate is NOT part of the user profile. But we can
        # translate the user profile to a suggested basal rate.

        pass
