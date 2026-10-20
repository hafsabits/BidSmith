import { createContext, ReactNode, useContext, useEffect, useState } from "react";

const KEY = "bidsmith.profile";

const ProfileContext = createContext<{ profileId: string; setProfileId: (id: string) => void }>({
  profileId: "ryan",
  setProfileId: () => {},
});

function readStored(): string {
  try {
    return localStorage.getItem(KEY) || "ryan";
  } catch {
    return "ryan";
  }
}

export function ProfileProvider({ children }: { children: ReactNode }) {
  const [profileId, setProfileId] = useState(readStored);
  useEffect(() => {
    try {
      localStorage.setItem(KEY, profileId);
    } catch {
      /* storage unavailable */
    }
  }, [profileId]);
  return <ProfileContext.Provider value={{ profileId, setProfileId }}>{children}</ProfileContext.Provider>;
}

export const useProfile = () => useContext(ProfileContext);
