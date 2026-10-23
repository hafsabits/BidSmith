import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, RunEvent } from "./api";

const FALLBACK_POLL_MS = 10_000;

/**
 * Run state driven by the server's event stream.
 *
 * The run is fetched once, then refetched only when an event says something changed
 * (a node finished or the status moved). Bursts of events, such as the replay on
 * connect, collapse into a single refetch. Polling happens only as a fallback while
 * the event stream is disconnected.
 */
export function useLiveRun(runId: string) {
  const queryClient = useQueryClient();
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [streamOk, setStreamOk] = useState(true);

  const query = useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.run(runId),
    refetchInterval: (q) => (!streamOk && q.state.data?.status === "running" ? FALLBACK_POLL_MS : false),
  });

  useEffect(() => {
    setEvents([]);
    setStreamOk(true);
    const source = new EventSource(api.eventsUrl(runId));
    let timer: number | undefined;
    const refresh = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => queryClient.invalidateQueries({ queryKey: ["run", runId] }), 250);
    };

    source.onopen = () => setStreamOk(true);
    source.onmessage = (msg) => {
      const event: RunEvent = JSON.parse(msg.data);
      setEvents((prev) => (prev.some((e) => e.seq === event.seq) ? prev : [...prev, event]));
      if (event.type !== "trace") refresh();
      if (event.type === "status" && (event.status === "done" || event.status === "error")) source.close();
    };
    // The browser reconnects on its own (resuming via Last-Event-ID); poll slowly meanwhile.
    source.onerror = () => {
      setStreamOk(false);
      refresh();
    };
    return () => {
      window.clearTimeout(timer);
      source.close();
    };
  }, [runId, queryClient]);

  return { run: query.data, events };
}
