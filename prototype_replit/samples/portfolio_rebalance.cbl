* ══════════════════════════════════════════════
   * PORTFOLIO REBALANCING ENGINE
   * Wealth Management — Core System
   * Last modified: 2004-11-22 by R. Takahashi
   * Batch cycle: Nightly 02:00 EST
   * WARNING: WASH-SALE-CHECK interacts with TAX-LOT
   *   subsystem via COPY TAXLOT-REC. Do not modify
   *   independently.
   * ══════════════════════════════════════════════
    IDENTIFICATION DIVISION.
    PROGRAM-ID. REBAL-ENGINE.

    DATA DIVISION.
    WORKING-STORAGE SECTION.
    01 WS-PORTFOLIO-REC.
       05 WS-ACCOUNT-ID        PIC X(12).
       05 WS-ASSET-CLASS        PIC X(4).
          88 EQUITY             VALUE 'EQTY'.
          88 FIXED-INCOME       VALUE 'FIXD'.
          88 CASH               VALUE 'CASH'.
       05 WS-TARGET-ALLOC       PIC 9(3)V99.
       05 WS-CURRENT-ALLOC      PIC 9(3)V99.
       05 WS-DRIFT-PCT          PIC S9(3)V99.
       05 WS-MARKET-VALUE       PIC 9(9)V99.
       05 WS-UNREALIZED-GL      PIC S9(9)V99.
       05 WS-HOLD-DAYS          PIC 9(5).
       05 WS-REBAL-ACTION       PIC X(4).
          88 BUY-ORDER          VALUE 'BUY '.
          88 SELL-ORDER         VALUE 'SELL'.
          88 HOLD-ORDER         VALUE 'HOLD'.
       05 WS-TRADE-AMOUNT       PIC 9(9)V99.

    01 WS-THRESHOLDS.
       05 WS-DRIFT-TRIGGER      PIC 9(3)V99 VALUE 5.00.
       05 WS-MIN-TRADE          PIC 9(7)V99 VALUE 50.00.
       05 WS-TLH-THRESHOLD      PIC S9(9)V99 VALUE -3000.00.
       05 WS-WASH-SALE-DAYS     PIC 9(3) VALUE 030.

    01 WS-REBAL-FLAG            PIC X(1).
       88 REBAL-NEEDED          VALUE 'Y'.
       88 REBAL-SKIP            VALUE 'N'.
    01 WS-TLH-FLAG              PIC X(1).
       88 TLH-TRIGGERED         VALUE 'Y'.
       88 TLH-SKIP              VALUE 'N'.
    01 WS-ERROR-CODE            PIC 9(4).
    01 WS-AUDIT-REASON          PIC X(40).

    PROCEDURE DIVISION.
    MAIN-REBALANCE.
        PERFORM CALC-DRIFT
        PERFORM CHECK-REBAL-TRIGGER
        IF REBAL-NEEDED
           PERFORM CHECK-TAX-LOSS-HARVEST
           PERFORM CHECK-WASH-SALE
           PERFORM CALC-TRADE
           PERFORM VALIDATE-MIN-TRADE
           PERFORM WRITE-REBAL-AUDIT
        ELSE
           SET HOLD-ORDER TO TRUE
           MOVE 'DRIFT WITHIN THRESHOLD' TO WS-AUDIT-REASON
           PERFORM WRITE-REBAL-AUDIT
        END-IF
        STOP RUN.

    CALC-DRIFT.
        SUBTRACT WS-TARGET-ALLOC FROM WS-CURRENT-ALLOC
           GIVING WS-DRIFT-PCT.

    CHECK-REBAL-TRIGGER.
   * BR: Rebalance only if absolute drift > threshold
        IF FUNCTION ABS(WS-DRIFT-PCT) >
           WS-DRIFT-TRIGGER
           SET REBAL-NEEDED TO TRUE
        ELSE
           SET REBAL-SKIP TO TRUE
        END-IF.

    CHECK-TAX-LOSS-HARVEST.
   * BR: If unrealized loss exceeds TLH threshold,
   *     prioritize selling losing positions
        IF WS-UNREALIZED-GL < WS-TLH-THRESHOLD
           SET TLH-TRIGGERED TO TRUE
           MOVE 'TLH OPPORTUNITY DETECTED' TO
              WS-AUDIT-REASON
        ELSE
           SET TLH-SKIP TO TRUE
        END-IF.

    CHECK-WASH-SALE.
   * BR: Block sale if position held < 30 days
   *     to avoid wash sale violation
        IF WS-HOLD-DAYS < WS-WASH-SALE-DAYS
           SET HOLD-ORDER TO TRUE
           SET REBAL-SKIP TO TRUE
           MOVE 'WASH SALE BLOCK — HOLD PERIOD'
              TO WS-AUDIT-REASON
           MOVE 2001 TO WS-ERROR-CODE
        END-IF.

    CALC-TRADE.
   * BR: Trade amount = market_value * abs(drift)
   *     Direction based on sign of drift
        MULTIPLY WS-MARKET-VALUE BY
           FUNCTION ABS(WS-DRIFT-PCT)
           GIVING WS-TRADE-AMOUNT
        DIVIDE WS-TRADE-AMOUNT BY 100
           GIVING WS-TRADE-AMOUNT
        IF WS-DRIFT-PCT > 0
           SET SELL-ORDER TO TRUE
        ELSE
           SET BUY-ORDER TO TRUE
        END-IF.

    VALIDATE-MIN-TRADE.
   * BR: Skip if trade below $50 — fee erosion
        IF WS-TRADE-AMOUNT < WS-MIN-TRADE
           SET HOLD-ORDER TO TRUE
           SET REBAL-SKIP TO TRUE
           MOVE 'BELOW MIN TRADE THRESHOLD'
              TO WS-AUDIT-REASON
        END-IF.

    WRITE-REBAL-AUDIT.
   * BR: Every rebalance decision logged for compliance
        WRITE AUDIT-RECORD FROM WS-PORTFOLIO-REC
        WRITE AUDIT-RECORD FROM WS-AUDIT-REASON.