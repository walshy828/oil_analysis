from datetime import date, timedelta, datetime
from typing import List, Dict, Optional
import logging
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import Location, OilOrder, TankReading, DailyUsage, Temperature

logger = logging.getLogger(__name__)

class UsageNormalizer:
    def __init__(self, db: Session):
        self.db = db

    def recalculate_usage(self, location_id: int, days: Optional[int] = None):
        """
        Rebuilds the DailyUsage table for a location.
        If days is provided, only deletes/recalculates for that recent history.
        """
        logger.info(f"Recalculating usage for location {location_id}, days={days}")
        
        start_limit = None
        if days:
            start_limit = date.today() - timedelta(days=days)
            
        # 0. Clean Data First
        self._clean_sensor_data(location_id, start_limit)
        
        # 1. Clear existing range
        if start_limit:
            self.db.query(DailyUsage).filter(
                DailyUsage.location_id == location_id,
                DailyUsage.date >= start_limit
            ).delete()
        else:
            self.db.query(DailyUsage).filter(DailyUsage.location_id == location_id).delete()
        
        # Fetch ALL orders to ensure continuity of intervals
        orders = self.db.query(OilOrder).filter(
            OilOrder.location_id == location_id
        ).order_by(OilOrder.start_date).all()
        
        if not orders:
            logger.warning(f"No orders for location {location_id}, falling back to raw sensor data")
            if not start_limit:
                 self._process_raw_sensor_only(location_id)
            else:
                 # Partial raw sensor?
                 self._process_raw_sensor_only(location_id, start_limit)
            return

        sorted_orders = sorted(orders, key=lambda x: x.start_date)
        prev_date = None
        
        for i, order in enumerate(sorted_orders):
            current_date = order.start_date
            
            if i == 0:
                # Logic for period before first order...
                # For now simplify: Skip pre-history if partial?
                start_date = current_date - timedelta(days=30) 
            else:
                start_date = sorted_orders[i-1].start_date
                
            # If doing partial update, skip intervals entirely before the limit
            if start_limit and current_date < start_limit:
                prev_date = current_date
                continue
                
            # If start_limit falls WITHIN this interval, we should theoretically partial-update,
            # but our logic distributes the WHOLE interval. Overwriting pre-limit days in this interval is fine (idempotent).
            
            self._distribute_usage(location_id, start_date, current_date, float(order.gallons))
            prev_date = current_date

        # Open ended period
        if prev_date:
            # If latest order was before start_limit, we still need to process the "open" period from start_limit
            normalization_start = prev_date
            if start_limit and prev_date < start_limit:
                # If the last order was long ago, we only care about usage since start_limit?
                # But normalize_open_ended depends on sensor data.
                pass
            
            self._process_open_ended_period(location_id, normalization_start)

        self.db.commit()

    def _clean_sensor_data(self, location_id: int, start_date: Optional[date]):
        """
        Pre-process tank readings to flag high-level noise as anomalies.
        """
        # Default to last year if no start date, or reasonably long history
        query_start = start_date if start_date else (date.today() - timedelta(days=365*2))
        end_date = date.today()
        
        logger.info(f"Scanning for high-level sensor noise since {query_start}")
        
        current = query_start
        while current <= end_date:
            next_day = current + timedelta(days=1)
            # Fetch valid readings
            readings = self.db.query(TankReading).filter(
                TankReading.location_id == location_id,
                TankReading.timestamp >= current,
                TankReading.timestamp < next_day,
                TankReading.is_anomaly == False
            ).all()
            
            if len(readings) > 3:
                vals = [float(r.gallons) for r in readings]
                avg = np.mean(vals)
                std_dev = np.std(vals)
                
                # NOISE CRITERIA:
                # 1. High Tank Level: > 225 gallons (Top zone where sensors struggle)
                # 2. High Variance: std_dev > 1.0 (Erratic readings)
                # If these conditions are met, the entire day's data is suspect.
                if avg > 225.0 and std_dev > 1.0:
                    logger.info(f"Marking {len(readings)} readings on {current} as high-level noise (Avg: {avg:.1f}, Std: {std_dev:.2f})")
                    for r in readings:
                        r.is_anomaly = True
            
            current += timedelta(days=1)
        self.db.commit()


    def _distribute_usage(self, location_id: int, start_date: date, end_date: date, target_gallons: float):
        """
        Distributes `target_gallons` across days [start_date, end_date).
        Uses Sensor Drop if available/reliable. Uses HDD if sensor missing/noisy.
        """
        days = (end_date - start_date).days
        if days <= 0: return

        # Fetch daily stats
        daily_stats = []
        
        total_sensor_drop = 0.0
        total_hdd = 0.0
        daily_stats = []
        
        k_factor = self._get_k_factor(location_id) # Need for fallback
        
        current = start_date
        while current < end_date:
            # Get HDD
            temp = self.db.query(Temperature).filter(
                Temperature.location_id == location_id,
                Temperature.date == current
            ).first()
            
            hdd = 0.0
            if temp and temp.high_temp is not None and temp.low_temp is not None:
                 avg = (float(temp.high_temp) + float(temp.low_temp)) / 2.0
                 hdd = max(0.0, 65.0 - avg)
            
            # Get Sensor Drop
            # Query readings for this day
            drop, is_unreliable, sensor_notes = self._get_daily_sensor_drop(location_id, current)
            raw_sensor = drop  # Store original value
            adjustment_reason = None
            
            if drop < 0:
                 adjustment_reason = 'fill_event'
                 sensor_notes += ' | Fill detected (level increase >20gal)'
                 drop = 0.0
                  
            # Fallback for Unreliable days in Closed Period
            if is_unreliable:
                 estimated_val = (hdd * k_factor) + 0.5
                 adjustment_reason = 'high_tank_noise'
                 sensor_notes += f' | Fallback to HDD estimate: {estimated_val:.2f}'
                 drop = estimated_val

            daily_stats.append({
                'date': current,
                'hdd': hdd,
                'sensor': drop,
                'raw_sensor': raw_sensor,
                'is_unreliable': is_unreliable,
                'adjustment_reason': adjustment_reason,
                'notes': sensor_notes
            })
            
            total_sensor_drop += drop
            total_hdd += hdd
            current += timedelta(days=1)
            
            # Strategy Selection
        
        # Confidence check
        ratio = total_sensor_drop / target_gallons if target_gallons > 0 else 0
        use_sensor = 0.5 < ratio < 1.5 and total_sensor_drop > 5.0
        
        source = 'sensor_adjusted' if use_sensor else 'hdd_estimated'
        
        # Calculate daily allocations
        # To support Summer Usage (Base Load), we refine the weighing.
        # Weight = (Relative Sensor Drop) OR (HDD * K + Base Load)
        
        total_estimated_load = 0
        daily_estimates = [] 
        base_load_daily = 0.5 # Gallons/day for Hot Water
        
        if not use_sensor:
             # Pre-calculate estimated load for HDD strategy
             for stat in daily_stats:
                 load = (stat['hdd'] * k_factor) + base_load_daily
                 daily_estimates.append(load)
                 total_estimated_load += load

        allocations = []
        for i, stat in enumerate(daily_stats):
            if use_sensor:
                # Shape by sensor, scale to target
                share = stat['sensor'] / total_sensor_drop if total_sensor_drop > 0 else 0
            else:
                # Shape by Estimated Load (HDD + Base), scale to target
                share = daily_estimates[i] / total_estimated_load if total_estimated_load > 0 else (1.0 / days)
            
            allocations.append({
                'date': stat['date'],
                'gallons': share * target_gallons,
                'source': source,
                'hdd': stat['hdd'],
                'raw_sensor': stat.get('raw_sensor', 0),
                'adjustment_reason': stat.get('adjustment_reason'),
                'notes': stat.get('notes', '')
            })
            
        # --- SAFEGUARD: Cap & Redistribute ---
        # Dynamic Cap based on Season/HDD
        # Winter: 15.0. Summer: 3.0 (to crush anomalies like 2.8g in June).
        
        excess_volume = 0.0
        capped_indices = set()
        
        for i, alloc in enumerate(allocations):
            # Determine Cap
            if alloc['hdd'] < 5:
                daily_cap = 2.0
            else:
                daily_cap = 15.0
                
            if alloc['gallons'] > daily_cap:
                alloc['pre_cap_value'] = alloc['gallons']
                diff = alloc['gallons'] - daily_cap
                excess_volume += diff
                alloc['gallons'] = daily_cap
                alloc['is_capped'] = True
                if not alloc.get('adjustment_reason'):
                    alloc['adjustment_reason'] = 'seasonal_cap'
                capped_indices.add(i)
        
        # 2. Redistribute excess to normal days (if any exist)
        if excess_volume > 0:
            uncapped_count = len(allocations) - len(capped_indices)
            if uncapped_count > 0:
                fill_amt = excess_volume / uncapped_count
                for i, alloc in enumerate(allocations):
                    if i not in capped_indices:
                        alloc['gallons'] += fill_amt
            else:
                logger.warning(f"Interval {start_date} to {end_date}: volume {target_gallons} exceeds max burn rate for all days.")
        # --- POST-PROCESSING: Contextual Spike Detection ---
        # Compare each day against its neighbors to detect anomalies
        allocations = self._smooth_contextual_spikes(allocations)
        
        # Bulk Insert with full documentation
        for alloc in allocations:
            notes_parts = [alloc.get('notes', '')]
            if alloc.get('is_capped'):
                notes_parts.append(f"Capped from {alloc.get('pre_cap_value', '?'):.2f} to {alloc['gallons']:.2f}")
            if alloc.get('spike_smoothed'):
                notes_parts.append(f"Spike smoothed from {alloc.get('pre_smooth_value', '?'):.2f}")
            
            final_notes = ' | '.join([n for n in notes_parts if n])
            
            rec = DailyUsage(
                location_id=location_id,
                date=alloc['date'],
                gallons=alloc['gallons'],
                is_estimated=(source != 'sensor_adjusted'),
                source=alloc.get('source', source),
                hdd=alloc['hdd'],
                raw_sensor_value=alloc.get('raw_sensor'),
                adjustment_reason=alloc.get('adjustment_reason'),
                notes=final_notes if final_notes else None
            )
            self.db.add(rec)


    def _get_k_factor(self, location_id: int) -> float:
        # Calculate recent efficiency (gallons per HDD)
        cutoff = date.today() - timedelta(days=90)
        stats = self.db.query(
            func.sum(DailyUsage.gallons),
            func.sum(DailyUsage.hdd)
        ).filter(
            DailyUsage.location_id == location_id,
            DailyUsage.date >= cutoff,
            DailyUsage.source.notlike('hdd%'), # Use only confirmed sensor data
            DailyUsage.gallons > 0
        ).first()
        
        if stats and stats[0] and stats[1] and float(stats[1]) > 50:
             val = float(stats[0]) / float(stats[1])
             return min(val, 0.4) # Reasonable cap
        return 0.15 # Default conservative (6 gal / 40 HDD)


    def _get_daily_sensor_drop(self, location_id: int, day: date) -> tuple[float, bool, str]:
        """
        Calculate raw drop in tank level for a specific day.
        Returns: (drop_gallons, is_unreliable, notes)
        """
        notes_parts = []
        
        # Get readings for this day + early next day to span full 24h
        next_day = day + timedelta(days=1)
        readings = self.db.query(TankReading).filter(
            TankReading.location_id == location_id,
            TankReading.timestamp >= day,
            TankReading.timestamp < next_day + timedelta(hours=4),
            TankReading.is_anomaly == False,
            TankReading.is_fill_event == False
        ).order_by(TankReading.timestamp).all()
        
        if not readings:
            return 0.0, True, 'No sensor readings available'
            
        vals = [float(r.gallons) for r in readings if r.timestamp.date() == day]
        if not vals or len(vals) < 5:
            return 0.0, False, f'Insufficient readings ({len(vals)})'
        
        n = len(vals)
        k = max(1, int(n * 0.20))
        
        start_level = np.median(vals[:k])
        end_level = np.median(vals[-k:])
        std_dev = np.std(vals)
        
        notes_parts.append(f'Readings: {n}, Start: {start_level:.1f}, End: {end_level:.1f}, Std: {std_dev:.2f}')
        
        # High Level Inaccuracy Check (> 230 gal)
        if start_level > 230.0:
            notes_parts.append('HIGH TANK: Sensor unreliable above 230gal')
            return 0.0, True, ' | '.join(notes_parts)

        # Fill Event Detection (level rise > 20 gal)
        if end_level > start_level + 20.0:
            notes_parts.append(f'FILL EVENT: Level rose {end_level - start_level:.1f}gal')
            return -1.0, False, ' | '.join(notes_parts)
        
        # Inverse Reading Check (End > Start = physically impossible for consumption)
        # If tank level appears to rise (even slightly), sensor data is unreliable
        if end_level > start_level + 0.5:  # Allow 0.5 gal tolerance for sensor noise
            notes_parts.append(f'SENSOR DRIFT: End ({end_level:.1f}) > Start ({start_level:.1f}) - data unreliable')
            return 0.0, True, ' | '.join(notes_parts)

        # Normal Consumption
        start_val = np.percentile(vals, 95)
        end_val = np.percentile(vals, 5)
        drop = float(max(0.0, start_val - end_val))
        
        notes_parts.append(f'P95-P05 drop: {drop:.2f}gal')
        
        return drop, False, ' | '.join(notes_parts)


    def _find_start_date_by_sensor_drop(self, location_id: int, end_date: date, target_drop: float) -> Optional[date]:
        # Walk back day by day, accumulating drop until match
        acc_drop = 0
        curr = end_date - timedelta(days=1)
        limit = end_date - timedelta(days=120) 
        
        while curr > limit:
            drop, _, _ = self._get_daily_sensor_drop(location_id, curr)
            acc_drop += drop
            if acc_drop >= target_drop * 0.9:
                return curr
            curr -= timedelta(days=1)
        return None

    def _process_raw_sensor_only(self, location_id: int, start_date: Optional[date] = None):
        # Fallback if no orders
        pass

    def _smooth_contextual_spikes(self, allocations: list) -> list:
        """
        Detect and smooth spikes by comparing each day against its neighbors.
        A spike is defined as usage > 2x the local median (7-day window).
        """
        if len(allocations) < 7:
            return allocations
        
        values = [a['gallons'] for a in allocations]
        
        for i in range(len(allocations)):
            # Define window (3 days before, 3 days after)
            start_idx = max(0, i - 3)
            end_idx = min(len(allocations), i + 4)
            window = values[start_idx:end_idx]
            
            # Exclude the current value from median calculation
            neighbors = [v for j, v in enumerate(window) if j != (i - start_idx)]
            if not neighbors:
                continue
            
            local_median = float(np.median(neighbors))
            current_val = float(allocations[i]['gallons'])
            
            # Spike Detection Criteria:
            # 1. Current value > 2x local median
            # 2. Current value > local median + 1.5 gallons (absolute threshold)
            # 3. Must exceed a minimum threshold (0.5) to avoid false positives on tiny values
            is_spike = (
                current_val > max(local_median * 2.0, local_median + 1.5) and
                current_val > 0.5
            )
            
            if is_spike:
                # Replace with interpolated value (average of neighbors)
                smoothed_val = float(np.mean(neighbors))
                allocations[i]['pre_smooth_value'] = current_val
                allocations[i]['gallons'] = smoothed_val
                allocations[i]['spike_smoothed'] = True
                if not allocations[i].get('adjustment_reason'):
                    allocations[i]['adjustment_reason'] = 'spike_smoothed'
                logger.info(f"Spike detected on {allocations[i]['date']}: {current_val:.2f} -> {smoothed_val:.2f} (median: {local_median:.2f})")
        
        return allocations

    def _process_open_ended_period(self, location_id: int, start_date: date):
        # From Last Order to Now
        # We don't have a target volume.
        # Use Raw Sensor, but maybe scale by K-factor from history?
        # For now, just Raw Sensor.
        end_date = date.today()
        if start_date >= end_date: return
        
        current = start_date
        allocations = []
        
        while current < end_date:
             drop, is_unreliable, sensor_notes = self._get_daily_sensor_drop(location_id, current)
             raw_sensor = drop
             adjustment_reason = None
             
             # Handle Fill Event in Open Period
             if drop < 0:
                 adjustment_reason = 'fill_event'
                 sensor_notes += ' | Fill detected'
                 drop = 0.0
             
             # Get HDD
             temp = self.db.query(Temperature).filter(
                Temperature.location_id == location_id,
                Temperature.date == current
             ).first()
             hdd = 0
             if temp and temp.high_temp and temp.low_temp:
                 hdd = max(0, 65 - (float(temp.high_temp) + float(temp.low_temp))/2.0)

             # Fallback for Unreliable High Level
             is_estimated_flag = False
             source_flag = 'sensor_raw'
             if is_unreliable:
                 k_factor = self._get_k_factor(location_id)
                 drop = (hdd * k_factor) + 0.5
                 is_estimated_flag = True
                 source_flag = 'hdd_estimated'
                 adjustment_reason = 'high_tank_noise'
                 sensor_notes += f' | Fallback to HDD estimate: {drop:.2f}'

             # Dynamic Cap for open-ended period
             if hdd < 5:
                 daily_cap = 2.0
             else:
                 daily_cap = 15.0
                 
             if drop > daily_cap:
                 sensor_notes += f' | Capped from {drop:.2f} to {daily_cap}'
                 adjustment_reason = 'seasonal_cap'
                 drop = daily_cap

             allocations.append({
                 'date': current,
                 'gallons': drop,
                 'hdd': hdd,
                 'is_estimated': is_estimated_flag,
                 'source': source_flag,
                 'raw_sensor': raw_sensor,
                 'adjustment_reason': adjustment_reason,
                 'notes': sensor_notes
             })
             current += timedelta(days=1)
        
        # Apply contextual spike smoothing
        allocations = self._smooth_contextual_spikes(allocations)
        
        # Insert records with full documentation
        for alloc in allocations:
             rec = DailyUsage(
                location_id=location_id,
                date=alloc['date'],
                gallons=alloc['gallons'],
                is_estimated=alloc['is_estimated'],
                source=alloc['source'],
                hdd=alloc['hdd'],
                raw_sensor_value=alloc.get('raw_sensor'),
                adjustment_reason=alloc.get('adjustment_reason'),
                notes=alloc.get('notes')
            )
             self.db.add(rec)

