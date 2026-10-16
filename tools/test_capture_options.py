import unittest
from capture_options import schedule


class ScheduleTests(unittest.TestCase):
    def test_default_follows_duration(self):
        self.assertEqual(schedule(12),[6])
    def test_repeat_csv_interval_sorted_and_deduplicated(self):
        self.assertEqual(schedule(12,['9,1','3,1'],3),[1,3,6,9,12])
    def test_fractional_endpoint_included(self):
        self.assertEqual(schedule(.3,every=.1),[.1,.2,.3])
    def test_zero_and_final_time_allowed(self):
        self.assertEqual(schedule(3,['3,0']),[0,3])
    def test_frame_limit_can_use_final_frame_capture(self):
        self.assertEqual(schedule(0,default=False),[])
    def test_rejects_invalid_schedules(self):
        for seconds,times,every in [(float('nan'),None,None),(3,['nan'],None),(3,['-1'],None),
                                    (3,['1,'],None),(3,['4'],None),(3,None,0),(3,None,float('inf')),
                                    (0,None,1),(3,None,4),(1e300,None,1e-300),(1,['0']*10001,None)]:
            with self.subTest(seconds=seconds,times=str(times)[:20],every=every):
                with self.assertRaises(ValueError):schedule(seconds,times,every)


if __name__=='__main__':unittest.main()
