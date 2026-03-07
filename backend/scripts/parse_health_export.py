#!/usr/bin/env python3
"""
Apple Health Export XML Parser

Extracts health data from Apple Health export.xml files and saves them to CSV files
for offline analysis. Includes: HRV, sleep, steps, resting HR, respiratory rate,
heart rate, and active energy burned.

Usage:
    python3 parse_health_export.py /path/to/export.xml [-o output_dir]
"""

import argparse
import csv
import os
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, TextIO


class HealthExportParser:
    """Streaming parser for Apple Health export XML files."""

    # Apple Health record type constants
    HRV_TYPE = "HKQuantityTypeIdentifierHeartRateVariabilitySDNN"
    SLEEP_TYPE = "HKCategoryTypeIdentifierSleepAnalysis"
    STEPS_TYPE = "HKQuantityTypeIdentifierStepCount"
    RESTING_HR_TYPE = "HKQuantityTypeIdentifierRestingHeartRate"
    RESPIRATORY_RATE_TYPE = "HKQuantityTypeIdentifierRespiratoryRate"
    HEART_RATE_TYPE = "HKQuantityTypeIdentifierHeartRate"
    ACTIVE_ENERGY_TYPE = "HKQuantityTypeIdentifierActiveEnergyBurned"

    # Sleep stage mapping
    SLEEP_STAGES = {
        "HKCategoryValueSleepAnalysisInBed": "In Bed",
        "HKCategoryValueSleepAnalysisAsleepUnspecified": "Asleep (Unspecified)",
        "HKCategoryValueSleepAnalysisAsleepCore": "Core Sleep",
        "HKCategoryValueSleepAnalysisAsleepDeep": "Deep Sleep",
        "HKCategoryValueSleepAnalysisAsleepREM": "REM Sleep",
        "HKCategoryValueSleepAnalysisAwake": "Awake",
    }

    # Sleep stages that count toward total sleep hours
    SLEEP_COUNTING_STAGES = {
        "HKCategoryValueSleepAnalysisAsleepCore",
        "HKCategoryValueSleepAnalysisAsleepDeep",
        "HKCategoryValueSleepAnalysisAsleepREM",
        "HKCategoryValueSleepAnalysisAsleepUnspecified",
    }

    def __init__(self, output_dir: Path):
        """Initialize parser with output directory."""
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Statistics tracking
        self.stats = {
            'hrv': {'count': 0, 'values': [], 'dates': []},
            'sleep': {'count': 0, 'total_hours': 0.0, 'stages': defaultdict(int), 'dates': set()},
            'steps': {'count': 0, 'total': 0, 'dates': set()},
            'resting_hr': {'count': 0, 'values': [], 'dates': []},
            'respiratory_rate': {'count': 0, 'values': [], 'dates': []},
            'heart_rate': {'count': 0, 'values': [], 'dates': []},
            'active_energy': {'count': 0, 'total': 0.0, 'dates': set()},
            'skipped': defaultdict(int)
        }

        # CSV file handles and writers (to be set up by caller)
        self.csv_files: Dict[str, TextIO] = {}
        self.csv_writers: Dict[str, csv.DictWriter] = {}

    def parse(self, export_file: Path) -> None:
        """Parse the export XML file and write CSVs."""
        print(f"Parsing {export_file}...")
        print(f"Output directory: {self.output_dir}")
        print()

        # Set up CSV files with ExitStack for Python 3.8 compatibility
        with ExitStack() as stack:
            # Open HRV CSV
            hrv_file = stack.enter_context(
                open(self.output_dir / 'hrv.csv', 'w', newline='')
            )
            hrv_writer = csv.DictWriter(hrv_file, fieldnames=['timestamp', 'value_ms'])
            hrv_writer.writeheader()
            self.csv_writers['hrv'] = hrv_writer

            # Open Sleep CSV
            sleep_file = stack.enter_context(
                open(self.output_dir / 'sleep.csv', 'w', newline='')
            )
            sleep_writer = csv.DictWriter(
                sleep_file,
                fieldnames=['start_time', 'end_time', 'duration_hours', 'sleep_stage']
            )
            sleep_writer.writeheader()
            self.csv_writers['sleep'] = sleep_writer

            # Open Steps CSV
            steps_file = stack.enter_context(
                open(self.output_dir / 'steps.csv', 'w', newline='')
            )
            steps_writer = csv.DictWriter(steps_file, fieldnames=['timestamp', 'step_count'])
            steps_writer.writeheader()
            self.csv_writers['steps'] = steps_writer

            # Open Resting Heart Rate CSV
            resting_hr_file = stack.enter_context(
                open(self.output_dir / 'resting_hr.csv', 'w', newline='')
            )
            resting_hr_writer = csv.DictWriter(resting_hr_file, fieldnames=['timestamp', 'bpm'])
            resting_hr_writer.writeheader()
            self.csv_writers['resting_hr'] = resting_hr_writer

            # Open Respiratory Rate CSV
            respiratory_rate_file = stack.enter_context(
                open(self.output_dir / 'respiratory_rate.csv', 'w', newline='')
            )
            respiratory_rate_writer = csv.DictWriter(respiratory_rate_file, fieldnames=['timestamp', 'breaths_per_min'])
            respiratory_rate_writer.writeheader()
            self.csv_writers['respiratory_rate'] = respiratory_rate_writer

            # Open Heart Rate CSV
            heart_rate_file = stack.enter_context(
                open(self.output_dir / 'heart_rate.csv', 'w', newline='')
            )
            heart_rate_writer = csv.DictWriter(heart_rate_file, fieldnames=['timestamp', 'bpm'])
            heart_rate_writer.writeheader()
            self.csv_writers['heart_rate'] = heart_rate_writer

            # Open Active Energy CSV
            active_energy_file = stack.enter_context(
                open(self.output_dir / 'active_energy.csv', 'w', newline='')
            )
            active_energy_writer = csv.DictWriter(active_energy_file, fieldnames=['timestamp', 'calories'])
            active_energy_writer.writeheader()
            self.csv_writers['active_energy'] = active_energy_writer

            # Parse XML with streaming to handle large files
            try:
                context = ET.iterparse(export_file, events=("end",))
                for event, elem in context:
                    if elem.tag == "Record":
                        self._handle_record(elem)
                        elem.clear()  # Free memory after processing each record

            except ET.ParseError as e:
                print(f"XML parse error: {e}", file=sys.stderr)
                sys.exit(1)

        # Print summary after parsing
        self._print_summary()

    def _handle_record(self, elem: ET.Element) -> None:
        """Dispatch record to appropriate handler based on type."""
        record_type = elem.get('type')

        if record_type == self.HRV_TYPE:
            self._handle_hrv(elem)
        elif record_type == self.SLEEP_TYPE:
            self._handle_sleep(elem)
        elif record_type == self.STEPS_TYPE:
            self._handle_steps(elem)
        elif record_type == self.RESTING_HR_TYPE:
            self._handle_resting_hr(elem)
        elif record_type == self.RESPIRATORY_RATE_TYPE:
            self._handle_respiratory_rate(elem)
        elif record_type == self.HEART_RATE_TYPE:
            self._handle_heart_rate(elem)
        elif record_type == self.ACTIVE_ENERGY_TYPE:
            self._handle_active_energy(elem)

    def _handle_hrv(self, elem: ET.Element) -> None:
        """Handle HRV record."""
        try:
            end_date = elem.get('endDate')
            value = elem.get('value')

            if not end_date or not value:
                self.stats['skipped']['hrv_missing_attrs'] += 1
                return

            # Parse timestamp
            timestamp = self._parse_datetime(end_date)
            if not timestamp:
                self.stats['skipped']['hrv_invalid_date'] += 1
                return

            # Parse value (in milliseconds)
            try:
                value_ms = float(value)
            except ValueError:
                self.stats['skipped']['hrv_invalid_value'] += 1
                return

            # Write to CSV
            self.csv_writers['hrv'].writerow({
                'timestamp': timestamp,
                'value_ms': value_ms
            })

            # Update stats
            self.stats['hrv']['count'] += 1
            self.stats['hrv']['values'].append(value_ms)
            self.stats['hrv']['dates'].append(timestamp.split()[0])

        except Exception as e:
            self.stats['skipped']['hrv_error'] += 1

    def _handle_sleep(self, elem: ET.Element) -> None:
        """Handle sleep record."""
        try:
            start_date = elem.get('startDate')
            end_date = elem.get('endDate')
            value = elem.get('value')

            if not start_date or not end_date or not value:
                self.stats['skipped']['sleep_missing_attrs'] += 1
                return

            # Parse timestamps
            start_time = self._parse_datetime(start_date)
            end_time = self._parse_datetime(end_date)
            if not start_time or not end_time:
                self.stats['skipped']['sleep_invalid_date'] += 1
                return

            # Map sleep stage
            sleep_stage = self.SLEEP_STAGES.get(
                value,
                f"Unknown ({value})"
            )

            # Calculate duration in hours
            try:
                start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S %z")
                end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S %z")
                duration_hours = (end_dt - start_dt).total_seconds() / 3600
            except Exception:
                self.stats['skipped']['sleep_duration_calc'] += 1
                return

            # Write to CSV
            self.csv_writers['sleep'].writerow({
                'start_time': start_time,
                'end_time': end_time,
                'duration_hours': f"{duration_hours:.4f}",
                'sleep_stage': sleep_stage
            })

            # Update stats
            self.stats['sleep']['count'] += 1
            self.stats['sleep']['stages'][sleep_stage] += 1

            # Only count certain stages toward total sleep hours
            if value in self.SLEEP_COUNTING_STAGES:
                self.stats['sleep']['total_hours'] += duration_hours

            # Track dates
            date = start_time.split()[0]
            self.stats['sleep']['dates'].add(date)

        except Exception as e:
            self.stats['skipped']['sleep_error'] += 1

    def _handle_steps(self, elem: ET.Element) -> None:
        """Handle step count record."""
        try:
            end_date = elem.get('endDate')
            value = elem.get('value')

            if not end_date or not value:
                self.stats['skipped']['steps_missing_attrs'] += 1
                return

            # Parse timestamp
            timestamp = self._parse_datetime(end_date)
            if not timestamp:
                self.stats['skipped']['steps_invalid_date'] += 1
                return

            # Parse value (handle "1234.0" format)
            try:
                step_count = int(float(value))
            except ValueError:
                self.stats['skipped']['steps_invalid_value'] += 1
                return

            # Write to CSV
            self.csv_writers['steps'].writerow({
                'timestamp': timestamp,
                'step_count': step_count
            })

            # Update stats
            self.stats['steps']['count'] += 1
            self.stats['steps']['total'] += step_count

            # Track dates
            date = timestamp.split()[0]
            self.stats['steps']['dates'].add(date)

        except Exception as e:
            self.stats['skipped']['steps_error'] += 1

    def _handle_resting_hr(self, elem: ET.Element) -> None:
        """Handle resting heart rate record."""
        try:
            end_date = elem.get('endDate')
            value = elem.get('value')

            if not end_date or not value:
                self.stats['skipped']['resting_hr_missing_attrs'] += 1
                return

            # Parse timestamp
            timestamp = self._parse_datetime(end_date)
            if not timestamp:
                self.stats['skipped']['resting_hr_invalid_date'] += 1
                return

            # Parse value (BPM)
            try:
                bpm = float(value)
            except ValueError:
                self.stats['skipped']['resting_hr_invalid_value'] += 1
                return

            # Write to CSV
            self.csv_writers['resting_hr'].writerow({
                'timestamp': timestamp,
                'bpm': bpm
            })

            # Update stats
            self.stats['resting_hr']['count'] += 1
            self.stats['resting_hr']['values'].append(bpm)
            self.stats['resting_hr']['dates'].append(timestamp.split()[0])

        except Exception as e:
            self.stats['skipped']['resting_hr_error'] += 1

    def _handle_respiratory_rate(self, elem: ET.Element) -> None:
        """Handle respiratory rate record."""
        try:
            end_date = elem.get('endDate')
            value = elem.get('value')

            if not end_date or not value:
                self.stats['skipped']['respiratory_rate_missing_attrs'] += 1
                return

            # Parse timestamp
            timestamp = self._parse_datetime(end_date)
            if not timestamp:
                self.stats['skipped']['respiratory_rate_invalid_date'] += 1
                return

            # Parse value (breaths per minute)
            try:
                breaths_per_min = float(value)
            except ValueError:
                self.stats['skipped']['respiratory_rate_invalid_value'] += 1
                return

            # Write to CSV
            self.csv_writers['respiratory_rate'].writerow({
                'timestamp': timestamp,
                'breaths_per_min': breaths_per_min
            })

            # Update stats
            self.stats['respiratory_rate']['count'] += 1
            self.stats['respiratory_rate']['values'].append(breaths_per_min)
            self.stats['respiratory_rate']['dates'].append(timestamp.split()[0])

        except Exception as e:
            self.stats['skipped']['respiratory_rate_error'] += 1

    def _handle_heart_rate(self, elem: ET.Element) -> None:
        """Handle heart rate record (raw HR data throughout the day)."""
        try:
            end_date = elem.get('endDate')
            value = elem.get('value')

            if not end_date or not value:
                self.stats['skipped']['heart_rate_missing_attrs'] += 1
                return

            # Parse timestamp
            timestamp = self._parse_datetime(end_date)
            if not timestamp:
                self.stats['skipped']['heart_rate_invalid_date'] += 1
                return

            # Parse value (BPM)
            try:
                bpm = float(value)
            except ValueError:
                self.stats['skipped']['heart_rate_invalid_value'] += 1
                return

            # Write to CSV
            self.csv_writers['heart_rate'].writerow({
                'timestamp': timestamp,
                'bpm': bpm
            })

            # Update stats
            self.stats['heart_rate']['count'] += 1
            self.stats['heart_rate']['values'].append(bpm)
            self.stats['heart_rate']['dates'].append(timestamp.split()[0])

        except Exception as e:
            self.stats['skipped']['heart_rate_error'] += 1

    def _handle_active_energy(self, elem: ET.Element) -> None:
        """Handle active energy burned record."""
        try:
            end_date = elem.get('endDate')
            value = elem.get('value')

            if not end_date or not value:
                self.stats['skipped']['active_energy_missing_attrs'] += 1
                return

            # Parse timestamp
            timestamp = self._parse_datetime(end_date)
            if not timestamp:
                self.stats['skipped']['active_energy_invalid_date'] += 1
                return

            # Parse value (calories)
            try:
                calories = float(value)
            except ValueError:
                self.stats['skipped']['active_energy_invalid_value'] += 1
                return

            # Write to CSV
            self.csv_writers['active_energy'].writerow({
                'timestamp': timestamp,
                'calories': calories
            })

            # Update stats
            self.stats['active_energy']['count'] += 1
            self.stats['active_energy']['total'] += calories

            # Track dates
            date = timestamp.split()[0]
            self.stats['active_energy']['dates'].add(date)

        except Exception as e:
            self.stats['skipped']['active_energy_error'] += 1

    def _parse_datetime(self, date_str: str) -> Optional[str]:
        """Parse Apple Health datetime string."""
        try:
            # Apple Health format: "2024-01-15 08:30:45 -0800"
            dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z")
            return dt.strftime("%Y-%m-%d %H:%M:%S %z")
        except ValueError:
            return None

    def _print_summary(self) -> None:
        """Print parsing summary statistics."""
        print("\n" + "="*60)
        print("PARSING SUMMARY")
        print("="*60)

        # HRV stats
        hrv_count = self.stats['hrv']['count']
        print(f"\nHRV (Heart Rate Variability):")
        print(f"  Records: {hrv_count:,}")
        if hrv_count > 0:
            values = self.stats['hrv']['values']
            print(f"  Average: {sum(values)/len(values):.2f} ms")
            print(f"  Min: {min(values):.2f} ms")
            print(f"  Max: {max(values):.2f} ms")
            dates = sorted(set(self.stats['hrv']['dates']))
            if dates:
                print(f"  Date range: {dates[0]} to {dates[-1]}")

        # Sleep stats
        sleep_count = self.stats['sleep']['count']
        print(f"\nSleep:")
        print(f"  Records: {sleep_count:,}")
        if sleep_count > 0:
            total_hours = self.stats['sleep']['total_hours']
            num_nights = len(self.stats['sleep']['dates'])
            print(f"  Total sleep hours: {total_hours:.2f}")
            if num_nights > 0:
                print(f"  Average per night: {total_hours/num_nights:.2f} hours")
            print(f"  Stage breakdown:")
            for stage, count in sorted(self.stats['sleep']['stages'].items()):
                print(f"    {stage}: {count:,} records")
            dates = sorted(self.stats['sleep']['dates'])
            if dates:
                print(f"  Date range: {dates[0]} to {dates[-1]}")

        # Steps stats
        steps_count = self.stats['steps']['count']
        print(f"\nSteps:")
        print(f"  Records: {steps_count:,}")
        if steps_count > 0:
            total_steps = self.stats['steps']['total']
            num_days = len(self.stats['steps']['dates'])
            print(f"  Total steps: {total_steps:,}")
            if num_days > 0:
                print(f"  Average daily: {total_steps/num_days:,.0f} steps")
            dates = sorted(self.stats['steps']['dates'])
            if dates:
                print(f"  Date range: {dates[0]} to {dates[-1]}")

        # Resting Heart Rate stats
        resting_hr_count = self.stats['resting_hr']['count']
        print(f"\nResting Heart Rate:")
        print(f"  Records: {resting_hr_count:,}")
        if resting_hr_count > 0:
            values = self.stats['resting_hr']['values']
            print(f"  Average: {sum(values)/len(values):.1f} bpm")
            print(f"  Min: {min(values):.1f} bpm")
            print(f"  Max: {max(values):.1f} bpm")
            dates = sorted(set(self.stats['resting_hr']['dates']))
            if dates:
                print(f"  Date range: {dates[0]} to {dates[-1]}")

        # Respiratory Rate stats
        respiratory_rate_count = self.stats['respiratory_rate']['count']
        print(f"\nRespiratory Rate:")
        print(f"  Records: {respiratory_rate_count:,}")
        if respiratory_rate_count > 0:
            values = self.stats['respiratory_rate']['values']
            print(f"  Average: {sum(values)/len(values):.1f} breaths/min")
            print(f"  Min: {min(values):.1f} breaths/min")
            print(f"  Max: {max(values):.1f} breaths/min")
            dates = sorted(set(self.stats['respiratory_rate']['dates']))
            if dates:
                print(f"  Date range: {dates[0]} to {dates[-1]}")

        # Heart Rate stats
        heart_rate_count = self.stats['heart_rate']['count']
        print(f"\nHeart Rate (Raw Data):")
        print(f"  Records: {heart_rate_count:,}")
        if heart_rate_count > 0:
            values = self.stats['heart_rate']['values']
            print(f"  Average: {sum(values)/len(values):.1f} bpm")
            print(f"  Min: {min(values):.1f} bpm")
            print(f"  Max: {max(values):.1f} bpm")
            dates = sorted(set(self.stats['heart_rate']['dates']))
            if dates:
                print(f"  Date range: {dates[0]} to {dates[-1]}")

        # Active Energy stats
        active_energy_count = self.stats['active_energy']['count']
        print(f"\nActive Energy Burned:")
        print(f"  Records: {active_energy_count:,}")
        if active_energy_count > 0:
            total_calories = self.stats['active_energy']['total']
            num_days = len(self.stats['active_energy']['dates'])
            print(f"  Total calories: {total_calories:,.1f}")
            if num_days > 0:
                print(f"  Average daily: {total_calories/num_days:,.1f} calories")
            dates = sorted(self.stats['active_energy']['dates'])
            if dates:
                print(f"  Date range: {dates[0]} to {dates[-1]}")

        # Skipped records
        total_skipped = sum(self.stats['skipped'].values())
        if total_skipped > 0:
            print(f"\nSkipped records: {total_skipped:,}")
            for reason, count in sorted(self.stats['skipped'].items()):
                print(f"  {reason}: {count:,}")

        print("\n" + "="*60)
        print(f"Output files written to: {self.output_dir}")
        print("  - hrv.csv")
        print("  - sleep.csv")
        print("  - steps.csv")
        print("  - resting_hr.csv")
        print("  - respiratory_rate.csv")
        print("  - heart_rate.csv")
        print("  - active_energy.csv")
        print("="*60 + "\n")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Parse Apple Health export XML and extract health data to CSV files. "
                    "Includes: HRV, sleep, steps, resting HR, respiratory rate, heart rate, and active energy.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 parse_health_export.py ~/Downloads/export.xml
  python3 parse_health_export.py ~/Downloads/export.xml -o ./my_data
        """
    )

    parser.add_argument(
        'export_file',
        type=Path,
        help='Path to Apple Health export.xml file'
    )

    parser.add_argument(
        '-o', '--output-dir',
        type=Path,
        default=Path('backend/data'),
        help='Output directory for CSV files (default: backend/data/)'
    )

    args = parser.parse_args()

    # Validate input file
    if not args.export_file.exists():
        print(f"Error: File not found: {args.export_file}", file=sys.stderr)
        sys.exit(1)

    if not args.export_file.is_file():
        print(f"Error: Not a file: {args.export_file}", file=sys.stderr)
        sys.exit(1)

    # Warn if file doesn't have .xml extension
    if args.export_file.suffix.lower() != '.xml':
        print(f"Warning: File does not have .xml extension: {args.export_file}")
        print("If this is a .zip file, please extract it first.")
        response = input("Continue anyway? [y/N] ")
        if response.lower() != 'y':
            sys.exit(0)

    # Parse the file
    parser_instance = HealthExportParser(args.output_dir)
    parser_instance.parse(args.export_file)


if __name__ == '__main__':
    main()
