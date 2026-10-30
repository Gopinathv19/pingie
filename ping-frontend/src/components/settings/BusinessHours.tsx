"use client";

import { Toggle } from "@/components/ui/Toggle";
import type { BusinessHours as Hours, Weekday } from "@/lib/types";
import s from "./settings.module.css";

const DAYS: [Weekday, string][] = [
  ["mon", "Monday"],
  ["tue", "Tuesday"],
  ["wed", "Wednesday"],
  ["thu", "Thursday"],
  ["fri", "Friday"],
  ["sat", "Saturday"],
  ["sun", "Sunday"],
];
const WEEKDAYS: Weekday[] = ["mon", "tue", "wed", "thu", "fri"];
const DEFAULT_RANGE: [string, string] = ["09:00", "18:00"];

function zones(current: string): string[] {
  const all = typeof Intl.supportedValuesOf === "function" ? Intl.supportedValuesOf("timeZone") : [];
  return all.includes(current) ? all : [current, ...all];
}

/** When the team takes chats. Outside these hours a handover is flagged and emailed instead. */
export function BusinessHours({ value, onChange }: { value: Hours; onChange: (v: Hours) => void }) {
  const setDay = (day: Weekday, range: [string, string] | null) => {
    const days = { ...value.days };
    if (range) days[day] = [range];
    else delete days[day];
    onChange({ ...value, days });
  };
  const copyMonday = () => {
    const monday = value.days.mon?.[0];
    if (!monday) return;
    onChange({ ...value, days: { ...value.days, ...Object.fromEntries(WEEKDAYS.map((d) => [d, [monday]])) } });
  };

  return (
    <div className="panel-body" style={{ maxWidth: 760 }}>
      <div className="toggle-row">
        <div>
          <span className="field-label">Only take chats during business hours</span>
          <span className="field-help">
            Outside these hours a visitor asking for a person is told when you&apos;re back, and the chat is flagged and
            emailed, even if someone has Live on.
          </span>
        </div>
        <Toggle
          label="Only take chats during business hours"
          checked={value.enabled}
          onChange={(enabled) => onChange({ ...value, enabled, days: enabled && !Object.keys(value.days).length ? Object.fromEntries(WEEKDAYS.map((d) => [d, [DEFAULT_RANGE]])) : value.days })}
        />
      </div>
      {value.enabled && (
        <>
          <label className="field" style={{ maxWidth: 360 }}>
            <span className="field-label">Time zone</span>
            <select className="select" value={value.timezone} onChange={(e) => onChange({ ...value, timezone: e.target.value })}>
              {zones(value.timezone).map((z) => (
                <option key={z} value={z}>
                  {z.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </label>
          <div className={s.hours}>
            {DAYS.map(([day, label]) => {
              const range = value.days[day]?.[0];
              return (
                <div key={day} className={s.hoursRow}>
                  <label className={s.hoursDay}>
                    <input type="checkbox" checked={!!range} onChange={(e) => setDay(day, e.target.checked ? DEFAULT_RANGE : null)} />
                    {label}
                  </label>
                  {range ? (
                    <span className={s.hoursTimes}>
                      <input
                        className="input"
                        type="time"
                        value={range[0]}
                        aria-label={`${label} opens`}
                        onChange={(e) => setDay(day, [e.target.value, range[1]])}
                      />
                      <span className="subtle">to</span>
                      <input
                        className="input"
                        type="time"
                        value={range[1]}
                        aria-label={`${label} closes`}
                        onChange={(e) => setDay(day, [range[0], e.target.value])}
                      />
                      {range[0] >= range[1] && <span className={s.hoursError}>Closing must be after opening</span>}
                    </span>
                  ) : (
                    <span className="subtle">Closed</span>
                  )}
                </div>
              );
            })}
          </div>
          <button type="button" className="btn btn-sm" style={{ alignSelf: "flex-start" }} onClick={copyMonday} disabled={!value.days.mon}>
            Copy Monday to all weekdays
          </button>
        </>
      )}
    </div>
  );
}
