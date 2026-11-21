package compactfixture;

import basemod.BaseMod;
import basemod.interfaces.PostUpdateSubscriber;
import com.evacipated.cardcrawl.modthespire.lib.SpireInitializer;
import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.megacrit.cardcrawl.characters.AbstractPlayer;
import com.megacrit.cardcrawl.core.CardCrawlGame;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.neow.NeowRoom;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;

/** Read-only assertion of the unmodified starting wallet for an isolated directed run. */
@SpireInitializer
public final class ReadOnlyWalletFixture implements PostUpdateSubscriber {
    private static boolean registered;
    private final Path root;
    private final JsonObject reservation;
    private boolean armed = true;
    private int applications;

    public static synchronized void initialize() {
        if (!Boolean.getBoolean("spire.nativefixture.enable")) return;
        if (registered) throw new IllegalStateException("Duplicate fixture registration");
        registered = true;
        try { BaseMod.subscribe(new ReadOnlyWalletFixture()); }
        catch (Exception e) { throw new IllegalStateException("Neow fixture initialization refused", e); }
    }

    private static JsonObject json(Path path) throws Exception {
        byte[] bytes = Files.readAllBytes(FixtureContract.exactFile(path));
        return new JsonParser().parse(new String(bytes, StandardCharsets.UTF_8)).getAsJsonObject();
    }
    private static String digest(Path path) throws Exception {
        byte[] data = MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(FixtureContract.exactFile(path)));
        StringBuilder text = new StringBuilder();
        for (byte b : data) text.append(String.format("%02x", b & 255));
        return text.toString();
    }
    private ReadOnlyWalletFixture() throws Exception {
        root = FixtureContract.exactDirectory(System.getProperty("spire.nativefixture.root"));
        Path cwd = FixtureContract.exactDirectory(System.getProperty("user.dir"));
        Path home = FixtureContract.exactDirectory(System.getProperty("user.home"));
        if (!root.resolve("game").equals(cwd) || !root.resolve("home").equals(home)) throw new IllegalArgumentException("Wrong isolation");
        FixtureContract.validateIsolation(json(root.resolve("bridge/isolation_manifest.json")), root, cwd, home);
        Path declaration = root.resolve("fixture_config.json");
        if (!declaration.equals(Paths.get(System.getProperty("spire.nativefixture.config")))) throw new IllegalArgumentException("Wrong fixture path");
        JsonObject config = json(declaration);
        String caseId=FixtureContract.text(config,"case_id");
        String seed=FixtureContract.text(config,"seed");
        boolean chosen=("r4_fungi_59".equals(caseId) && "1P".equals(seed)) ||
                       ("r4_fungi_19".equals(caseId) && "J".equals(seed));
        if (!chosen
            || !root.getFileName().toString().equals(FixtureContract.text(config,"initialization_id"))
            || FixtureContract.integer(config,"fixture_gold") != 99 || FixtureContract.integer(config,"ascension") != 20
             || !"fixture".equals(FixtureContract.text(config,"sample_kind"))
            || !"THE_SILENT".equals(FixtureContract.text(config,"character")) || config.get("training_enabled").getAsBoolean())
            throw new IllegalArgumentException("Wrong scenario");
        Path reserved = root.resolve("fixture_reservation.json");
        reservation = json(reserved);
        if (!digest(declaration).equals(System.getProperty("spire.nativefixture.config_sha256"))
            || !digest(reserved).equals(System.getProperty("spire.nativefixture.reservation_sha256")))
            throw new IllegalArgumentException("Unpinned inputs");
        FixtureContract.validateReservation(reservation,config,digest(declaration),System.getProperty("spire.oracle.launch_id"));
        Files.write(root.resolve("fixture_claim.json"), new Gson().toJson(reservation).getBytes(StandardCharsets.UTF_8),
                StandardOpenOption.CREATE_NEW);
        receipt("armed", -1);
    }

    private void receipt(String status, int initialGold) throws Exception {
        JsonObject entry = new JsonObject();
        entry.addProperty("schema","neow-readonly-wallet-receipt-v1");
        entry.add("reservation",reservation);
        entry.addProperty("status",status);
        entry.addProperty("initializations",applications);
        entry.addProperty("starting_wallet",initialGold);
        entry.addProperty("configured_wallet",99);
        entry.addProperty("training_eligible",false);
        entry.addProperty("time_nanos",System.nanoTime());
        byte[] bytes = (new Gson().toJson(entry)+"\n").getBytes(StandardCharsets.UTF_8);
        Files.write(root.resolve("fixture_events.jsonl"),bytes,StandardOpenOption.CREATE,StandardOpenOption.APPEND);
        Path tmp=root.resolve("fixture_receipt.tmp");
        Files.write(tmp,bytes,StandardOpenOption.CREATE_NEW);
        Files.move(tmp,root.resolve("fixture_receipt.json"),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
    }

    @Override public void receivePostUpdate() {
        if (!armed || CardCrawlGame.dungeon == null || AbstractDungeon.player == null
                || !(AbstractDungeon.getCurrRoom() instanceof NeowRoom)) return;
        AbstractPlayer p=AbstractDungeon.player;
        armed = false;
        try {
            if (AbstractDungeon.ascensionLevel != 20 || p.chosenClass != AbstractPlayer.PlayerClass.THE_SILENT
                || p.gold != 99 || p.maxHealth != 66 || p.currentHealth !=59)
                throw new IllegalStateException("Unexpected A20 fixture starting character/economy");
            int original=p.gold;
            // Capture the existing native value. No game state is assigned.
            applications++;
            receipt("loaded_and_disabled",original);
        } catch (Exception e) {
            try { receipt("failed_no_retry",p.gold); }
            catch (Exception ioe) { throw new IllegalStateException("Cannot record fixture error",ioe); }
            throw new IllegalStateException("Native starting wallet assertion failed", e);
        }
    }
}
