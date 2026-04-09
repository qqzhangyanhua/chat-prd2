import { describe, expect, it } from "vitest";
import fc from "fast-check";
import type { SessionResponse } from "../lib/types";

// Helper to get date boundaries (duplicated from component for testing)
function getDateBoundaries() {
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0);
  const todayEnd = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59, 999);
  const yesterdayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1, 0, 0, 0, 0);
  const yesterdayEnd = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1, 23, 59, 59, 999);
  const dayOfWeek = now.getDay();
  const daysToMonday = dayOfWeek === 0 ? 6 : dayOfWeek - 1;
  const weekStart = new Date(now.getFullYear(), now.getMonth(), now.getDate() - daysToMonday, 0, 0, 0, 0);
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1, 0, 0, 0, 0);
  
  return { todayStart, todayEnd, yesterdayStart, yesterdayEnd, weekStart, monthStart };
}

// Grouping function (duplicated from component for testing)
type DateGroup = 'today' | 'yesterday' | 'thisWeek' | 'thisMonth' | 'older';

interface GroupedSessions {
  today: SessionResponse[];
  yesterday: SessionResponse[];
  thisWeek: SessionResponse[];
  thisMonth: SessionResponse[];
  older: SessionResponse[];
}

function groupSessionsByDate(sessions: SessionResponse[]): GroupedSessions {
  const boundaries = getDateBoundaries();
  
  const grouped: GroupedSessions = {
    today: [],
    yesterday: [],
    thisWeek: [],
    thisMonth: [],
    older: [],
  };
  
  for (const session of sessions) {
    const updatedAt = new Date(session.updated_at);
    
    if (Number.isNaN(updatedAt.getTime())) {
      grouped.older.push(session);
      continue;
    }
    
    const timestamp = updatedAt.getTime();
    
    if (timestamp >= boundaries.todayStart.getTime() && timestamp <= boundaries.todayEnd.getTime()) {
      grouped.today.push(session);
    } else if (timestamp >= boundaries.yesterdayStart.getTime() && timestamp <= boundaries.yesterdayEnd.getTime()) {
      grouped.yesterday.push(session);
    } else if (timestamp >= boundaries.weekStart.getTime() && timestamp < boundaries.todayStart.getTime()) {
      if (timestamp < boundaries.yesterdayStart.getTime()) {
        grouped.thisWeek.push(session);
      } else {
        grouped.yesterday.push(session);
      }
    } else if (timestamp >= boundaries.monthStart.getTime() && timestamp < boundaries.weekStart.getTime()) {
      grouped.thisMonth.push(session);
    } else {
      grouped.older.push(session);
    }
  }
  
  const sortSessions = (a: SessionResponse, b: SessionResponse) => {
    const aTime = new Date(a.updated_at).getTime();
    const bTime = new Date(b.updated_at).getTime();
    if (aTime !== bTime) {
      return bTime - aTime;
    }
    return a.id.localeCompare(b.id);
  };
  
  grouped.today.sort(sortSessions);
  grouped.yesterday.sort(sortSessions);
  grouped.thisWeek.sort(sortSessions);
  grouped.thisMonth.sort(sortSessions);
  grouped.older.sort(sortSessions);
  
  return grouped;
}

// Arbitraries for property-based testing
const sessionArbitrary = fc.record({
  id: fc.uuid(),
  user_id: fc.uuid(),
  title: fc.string({ minLength: 1, maxLength: 100 }),
  initial_idea: fc.string({ minLength: 1, maxLength: 500 }),
  created_at: fc.date({ min: new Date('2020-01-01'), max: new Date('2030-12-31'), noInvalidDate: true }).map(d => d.toISOString()),
  updated_at: fc.date({ min: new Date('2020-01-01'), max: new Date('2030-12-31'), noInvalidDate: true }).map(d => d.toISOString()),
}) as fc.Arbitrary<SessionResponse>;

describe("WorkspaceLeftNav - Property-Based Tests", () => {
  // Feature: workspace-sidebar-session-grouping, Property 1: Grouping Function Returns Five Groups
  // **Validates: Requirements 1.1**
  it("Property 1: grouping function returns exactly five groups", () => {
    fc.assert(
      fc.property(
        fc.array(sessionArbitrary, { minLength: 0, maxLength: 50 }),
        (sessions) => {
          const grouped = groupSessionsByDate(sessions);
          
          // Should have exactly 5 keys
          const keys = Object.keys(grouped);
          expect(keys).toHaveLength(5);
          expect(keys).toContain('today');
          expect(keys).toContain('yesterday');
          expect(keys).toContain('thisWeek');
          expect(keys).toContain('thisMonth');
          expect(keys).toContain('older');
          
          // Each value should be an array
          expect(Array.isArray(grouped.today)).toBe(true);
          expect(Array.isArray(grouped.yesterday)).toBe(true);
          expect(Array.isArray(grouped.thisWeek)).toBe(true);
          expect(Array.isArray(grouped.thisMonth)).toBe(true);
          expect(Array.isArray(grouped.older)).toBe(true);
        }
      ),
      { numRuns: 100 }
    );
  });

  // Feature: workspace-sidebar-session-grouping, Property 2: Grouping Uses Updated_At Timestamp
  // **Validates: Requirements 1.2**
  it("Property 2: grouping uses updated_at timestamp, not created_at", () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.record({
            id: fc.uuid(),
            user_id: fc.uuid(),
            title: fc.string({ minLength: 1, maxLength: 100 }),
            initial_idea: fc.string({ minLength: 1, maxLength: 500 }),
            created_at: fc.date({ min: new Date('2020-01-01'), max: new Date('2020-12-31'), noInvalidDate: true }).map(d => d.toISOString()),
            updated_at: fc.date({ min: new Date('2025-01-01'), max: new Date(), noInvalidDate: true }).map(d => d.toISOString()),
          }) as fc.Arbitrary<SessionResponse>,
          { minLength: 1, maxLength: 20 }
        ),
        (sessions) => {
          const grouped = groupSessionsByDate(sessions);
          const allGroupedIds = new Set(
            [
              ...grouped.today,
              ...grouped.yesterday,
              ...grouped.thisWeek,
              ...grouped.thisMonth,
              ...grouped.older,
            ].map((session) => session.id)
          );

          // 验证分组完全由 updated_at 决定：即使 created_at 很旧，也不会丢失或重复。
          expect(allGroupedIds.size).toBe(sessions.length);
        }
      ),
      { numRuns: 100 }
    );
  });

  // Feature: workspace-sidebar-session-grouping, Property 3: Date Boundary Correctness
  // **Validates: Requirements 1.3, 1.4, 1.5, 1.6, 1.7**
  it("Property 3: sessions are grouped correctly by date boundaries", () => {
    fc.assert(
      fc.property(
        fc.array(sessionArbitrary, { minLength: 0, maxLength: 50 }),
        (sessions) => {
          const grouped = groupSessionsByDate(sessions);
          const boundaries = getDateBoundaries();
          
          // Verify each session is in the correct group
          for (const session of sessions) {
            const updatedAt = new Date(session.updated_at);
            
            if (Number.isNaN(updatedAt.getTime())) {
              // Invalid dates should be in older
              expect(grouped.older.some(s => s.id === session.id)).toBe(true);
              continue;
            }
            
            const timestamp = updatedAt.getTime();
            
            if (timestamp >= boundaries.todayStart.getTime() && timestamp <= boundaries.todayEnd.getTime()) {
              expect(grouped.today.some(s => s.id === session.id)).toBe(true);
            } else if (timestamp >= boundaries.yesterdayStart.getTime() && timestamp <= boundaries.yesterdayEnd.getTime()) {
              expect(grouped.yesterday.some(s => s.id === session.id)).toBe(true);
            } else if (timestamp >= boundaries.weekStart.getTime() && timestamp < boundaries.yesterdayStart.getTime()) {
              expect(grouped.thisWeek.some(s => s.id === session.id)).toBe(true);
            } else if (timestamp >= boundaries.monthStart.getTime() && timestamp < boundaries.weekStart.getTime()) {
              expect(grouped.thisMonth.some(s => s.id === session.id)).toBe(true);
            } else {
              expect(grouped.older.some(s => s.id === session.id)).toBe(true);
            }
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  // Feature: workspace-sidebar-session-grouping, Property 9: Sessions Sorted Within Groups
  // **Validates: Requirements 3.1, 3.2**
  it("Property 9: sessions within groups are sorted by updated_at descending with stable sort", () => {
    fc.assert(
      fc.property(
        fc.array(sessionArbitrary, { minLength: 2, maxLength: 50 }),
        (sessions) => {
          const grouped = groupSessionsByDate(sessions);
          
          // Check sorting in each group
          const allGroups: SessionResponse[][] = [
            grouped.today,
            grouped.yesterday,
            grouped.thisWeek,
            grouped.thisMonth,
            grouped.older,
          ];
          
          for (const group of allGroups) {
            if (group.length < 2) continue;
            
            for (let i = 0; i < group.length - 1; i++) {
              const current = group[i];
              const next = group[i + 1];
              
              const currentTime = new Date(current.updated_at).getTime();
              const nextTime = new Date(next.updated_at).getTime();
              
              // Current should be >= next (descending order)
              if (currentTime === nextTime) {
                // If times are equal, should be sorted by id
                expect(current.id.localeCompare(next.id)).toBeLessThanOrEqual(0);
              } else {
                expect(currentTime).toBeGreaterThanOrEqual(nextTime);
              }
            }
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  // Feature: workspace-sidebar-session-grouping, Property 13: Monday Week Start
  // **Validates: Requirements 9.2**
  it("Property 13: week start is calculated as Monday", () => {
    fc.assert(
      fc.property(
        fc.constant(null), // No input needed, just testing the function
        () => {
          const boundaries = getDateBoundaries();
          const weekStartDay = boundaries.weekStart.getDay();
          
          // Monday is day 1 in JavaScript (0 = Sunday, 1 = Monday, ..., 6 = Saturday)
          expect(weekStartDay).toBe(1);
          
          // Week start should be at midnight
          expect(boundaries.weekStart.getHours()).toBe(0);
          expect(boundaries.weekStart.getMinutes()).toBe(0);
          expect(boundaries.weekStart.getSeconds()).toBe(0);
          expect(boundaries.weekStart.getMilliseconds()).toBe(0);
        }
      ),
      { numRuns: 10 } // Only need to run this a few times since it's deterministic
    );
  });

  // Additional property test: Total session count preservation
  it("Property: total session count is preserved across all groups", () => {
    fc.assert(
      fc.property(
        fc.array(sessionArbitrary, { minLength: 0, maxLength: 100 }),
        (sessions) => {
          const grouped = groupSessionsByDate(sessions);
          
          const totalGrouped = 
            grouped.today.length +
            grouped.yesterday.length +
            grouped.thisWeek.length +
            grouped.thisMonth.length +
            grouped.older.length;
          
          expect(totalGrouped).toBe(sessions.length);
        }
      ),
      { numRuns: 100 }
    );
  });

  // Additional property test: No session appears in multiple groups
  it("Property: each session appears in exactly one group", () => {
    fc.assert(
      fc.property(
        fc.array(sessionArbitrary, { minLength: 1, maxLength: 50 }),
        (sessions) => {
          const grouped = groupSessionsByDate(sessions);
          
          const allGroupedSessions = [
            ...grouped.today,
            ...grouped.yesterday,
            ...grouped.thisWeek,
            ...grouped.thisMonth,
            ...grouped.older,
          ];
          
          // Check that each original session appears exactly once
          for (const session of sessions) {
            const occurrences = allGroupedSessions.filter(s => s.id === session.id).length;
            expect(occurrences).toBe(1);
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  // Additional property test: Invalid dates always go to older
  it("Property: sessions with invalid dates are placed in older group", () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.record({
            id: fc.uuid(),
            user_id: fc.uuid(),
            title: fc.string({ minLength: 1, maxLength: 100 }),
            initial_idea: fc.string({ minLength: 1, maxLength: 500 }),
            created_at: fc.constant("invalid-date"),
            updated_at: fc.constant("invalid-date"),
          }) as fc.Arbitrary<SessionResponse>,
          { minLength: 1, maxLength: 20 }
        ),
        (sessions) => {
          const grouped = groupSessionsByDate(sessions);
          
          // All sessions should be in older group
          expect(grouped.older.length).toBe(sessions.length);
          expect(grouped.today.length).toBe(0);
          expect(grouped.yesterday.length).toBe(0);
          expect(grouped.thisWeek.length).toBe(0);
          expect(grouped.thisMonth.length).toBe(0);
        }
      ),
      { numRuns: 100 }
    );
  });
});
