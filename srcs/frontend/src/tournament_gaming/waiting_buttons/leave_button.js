import { AreYouSureModal } from "../utils.js";
import showToast from "../../utils/toast.js";
import showLoadingSpinner from "../../utils/spinner.js";
import renderHeader from '../../components/header.js';
import renderTournaments from '../../pages/tournaments/tournaments.js';
import { fetchWithAuth } from "../../utils/fetchWithAuth.js";

export default async function leaveButton(socket, tournamentId)
{
    const modal = AreYouSureModal();
    document.body.appendChild(modal);

    const yesBtn = document.getElementById('yesBtn');
    const noBtn = document.getElementById('noBtn');

    yesBtn.addEventListener('click', () => {
        leaveTournament(socket, tournamentId);
        document.body.removeChild(modal);
    });

    noBtn.addEventListener('click', () => {
        document.body.removeChild(modal);
    });
}

async function leaveTournament(socket, tournamentId)
{
    try
    {        
        showLoadingSpinner(true);
        const url = `/api/games/tournament/leave/`;
        const response = await fetchWithAuth(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                tournament_id: tournamentId
            }),
        });
    
        const result = await response.json();
        
        if (!response.ok)
            showToast(result.error, 'error');
        else
        {
            socket.send(JSON.stringify({event: 'user_left'}));
            await renderHeader();
            renderTournaments();
        }
    }
    catch (error)
    {
        showToast('An error occurred while leaving the tournament.', 'error');
    }
    finally
    {
        showLoadingSpinner(false);
    }
}